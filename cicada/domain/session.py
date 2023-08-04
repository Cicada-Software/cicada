from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import NewType
from uuid import UUID

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

        return self not in (Status.BOOTING, Status.PENDING)

    def is_failure(self) -> bool:
        """
        A "failure" means any unsuccessful status, ie, STOPPED or FAILURE.
        """

        return self in (Status.FAILURE, Status.STOPPED)


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
    """

    id: WorkflowId
    filename: Path
    sha: GitSha
    status: WorkflowStatus
    started_at: UtcDatetime = field(default_factory=UtcDatetime.now)
    finished_at: UtcDatetime | None = None
    # TODO: make this immutable/frozen
    run_on_self_hosted: bool = False


@dataclass
class Run:
    """
    A run encapsulates a collection of workflows that are part of a session. A
    run is represented as a dictionary, where the key is the filename of the
    workflow, and the value is a list of workflows for the current run. When a
    session is first started, a run will contain N items for each of the N
    workflows to be ran. Since the session was just started, each list will
    only have 1 workflow in it.

    When you rerun a session, a new run object is created. If you don't want to
    rerun all workflows for a particular run though (say only one failed), you
    can rerun only a particular workflow in that run. When you do so, the new
    workflow will be appended to the list of workflows with the same name. The
    index of the workflow in the list indicates the order in which it was ran:
    the oldest workflows are at the start, the newest ones at the end.
    """

    workflows: dict[Path, list[Workflow]]

    def __post_init__(self) -> None:
        for workflows in self.workflows.values():
            if not workflows:
                raise ValueError("Expected list of workflows")


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
    run_on_self_hosted: bool = False

    def __post_init__(self) -> None:
        assert self.run >= 1

    def finish(self, status: SessionStatus) -> None:
        self.status = status
        self.finished_at = UtcDatetime.now()
