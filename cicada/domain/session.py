from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import NewType, Self
from uuid import UUID, uuid4

from cicada.domain.datetime import UtcDatetime

from .triggers import GitSha, Trigger


class Status(Enum):
    BOOTING = "BOOTING"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    STOPPED = "STOPPED"

    def is_finished(self) -> bool:
        """
        A "finished" status means that the status is final, ie, a success or a
        failure.
        """

        return self not in {Status.BOOTING, Status.PENDING}

    def is_failure(self) -> bool:
        """
        A "failure" means any unsuccessful status, ie, STOPPED or FAILURE.
        """

        return self in {Status.FAILURE, Status.STOPPED}


SessionStatus = Status
WorkflowStatus = Status

# TODO: use typing.NewType
SessionId = UUID

WorkflowId = NewType("WorkflowId", UUID)


@dataclass
class Workflow:
    """
    A workflow run. This object represents the running of a workflow file, and
    contains important data such as start/finish time, status, sha and path of
    the file, and so forth.

    A workflow is singular, meaning that if you want to "rerun" a workflow, a
    new workflow is created. Once a workflow is finished, it shouldn't be need
    to be updated again.

    Workflows can spawn sub-workflows, allowing for features such as matrix
    builds. Sub workflows are scoped to the workflow that spawned them, meaning
    they are still scoped to the same session as their parent.
    """

    id: WorkflowId
    filename: Path
    sha: GitSha
    status: WorkflowStatus
    started_at: UtcDatetime = field(default_factory=UtcDatetime.now)
    finished_at: UtcDatetime | None = None
    # TODO: make this immutable/frozen
    run_on_self_hosted: bool = False
    title: str | None = None

    parent: WorkflowId | None = None
    sub_workflows: list["Workflow"] = field(default_factory=list)

    def finish(self, status: WorkflowStatus) -> None:
        self.status = status
        self.finished_at = UtcDatetime.now()

    @classmethod
    def from_session(
        cls,
        session: "Session",
        *,
        filename: Path,
        run_on_self_hosted: bool = False,
        title: str | None = None,
    ) -> Self:
        """
        Create a workflow object from a session. This is meant as a placeholder until sessions and
        workflows are more distinct.
        """

        assert session.trigger.sha

        return cls(
            id=WorkflowId(uuid4()),
            filename=filename,
            sha=session.trigger.sha,
            status=session.status,
            started_at=session.started_at,
            finished_at=session.finished_at,
            run_on_self_hosted=run_on_self_hosted,
            title=title,
        )

    def make_subworkflow(self) -> "Workflow":
        return Workflow(
            id=WorkflowId(uuid4()),
            filename=self.filename,
            sha=self.sha,
            status=WorkflowStatus.PENDING,
            started_at=UtcDatetime.now(),
            finished_at=None,
            run_on_self_hosted=self.run_on_self_hosted,
            title=self.title,
            parent=self.id,
        )


@dataclass
class Session:
    """
    A session is created whenever an event is triggered. A session is where all
    the runs (and thus the workflows) are attached.

    Sessions are currently getting a rework, and the exact behaviour will be
    changing soon. Previously, there where no concept of "workflows", and
    everything was a session. The ability to rerun sessions was added, which
    would create a new session with the same id, but would have a "run" count
    that would be incremented for each rerun. This will change soon, with a
    session only acting as a container/wrapper for all the workflows, and
    the runs/workflows being responsible for the rerun and start/finish logic.
    """

    id: SessionId
    trigger: Trigger
    status: SessionStatus = SessionStatus.PENDING
    started_at: UtcDatetime = field(default_factory=UtcDatetime.now)
    finished_at: UtcDatetime | None = None
    run: int = 1

    # TODO: deprecate run
    runs: list[Workflow] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        assert self.run >= 1

        if self.status.is_finished():
            assert self.finished_at

        if self.finished_at:
            assert self.status.is_finished()

    def finish(self) -> None:
        if not self.runs:
            # TODO: sessions shouldn't be finished unless they have workflows
            return

        root_workflow = self.runs[self.run - 1]
        failure_status: SessionStatus | None = None

        def walk(workflow: Workflow) -> None:
            nonlocal failure_status

            if not self.finished_at or (
                workflow.finished_at and workflow.finished_at > self.finished_at
            ):
                self.finished_at = workflow.finished_at

            # TODO: how to differenctiate between multiple different failure statuses?
            if workflow.status.is_failure():
                failure_status = workflow.status

            for sub_workflow in workflow.sub_workflows:
                walk(sub_workflow)

        walk(root_workflow)

        self.status = failure_status or SessionStatus.SUCCESS
        self.validate()
