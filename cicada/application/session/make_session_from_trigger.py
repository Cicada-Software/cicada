import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from cicada.application.secret.gather_secrets_from_trigger import (
    GatherSecretsFromTrigger,
)
from cicada.application.session.common import (
    IWorkflowGatherer,
    IWorkflowRunner,
)
from cicada.ast.nodes import FileNode, RunOnStatement, RunType
from cicada.domain.repo.environment_repo import IEnvironmentRepo
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.services.repository import get_env_vars_for_repo
from cicada.domain.session import Session, SessionStatus
from cicada.domain.triggers import Trigger
from cicada.eval.constexpr_visitor import eval_title


class MakeSessionFromTrigger:
    """
    This is probably one of the most important application services, since this
    service is responsible for starting workflows from triggers such as a git
    push, an issue being open, etc.

    This service takes many different repository interfaces:

    session_repo, terminal_session_repo, env_repo, repository_repo: All of
    these are repository interfaces for querying data, and are pretty self
    explanatory.

    gather_workflows: This is an async callback which returns a list of
    `.ci` workflow files that need to be ran. An empty list indicates that
    no workflows where found, and the application does nothing.

    workflow_runner: This is a coroutine which actually runs the workflow.
    The Session argument includes the start time, and the caller is responsible
    for setting the stop time and status (an AssertionError is thrown if these
    are not set). The TerminalSession argument is for streaming the stdout
    of the program back to Cicada so that it can be displayed to the user.

    One of the current limitations to this service is that it is not capable
    of running multiple workflows from one trigger. Basically, if there are 2
    files which contain the same trigger, say `git.push`, then an exception is
    thrown. The reason being that there is no way in the UI to show multiple
    workflows for a single session, or link a particular session to the
    workflow file(s) that it is currently running.
    """

    def __init__(
        self,
        session_repo: ISessionRepo,
        terminal_session_repo: ITerminalSessionRepo,
        workflow_runner: IWorkflowRunner,
        gather_workflows: IWorkflowGatherer,
        env_repo: IEnvironmentRepo,
        repository_repo: IRepositoryRepo,
        installation_repo: IInstallationRepo,
        secret_repo: ISecretRepo,
    ) -> None:
        self.session_repo = session_repo
        self.terminal_session_repo = terminal_session_repo
        self.workflow_runner = workflow_runner
        self.gather_workflows = gather_workflows
        self.env_repo = env_repo
        self.repository_repo = repository_repo
        self.installation_repo = installation_repo
        self.secret_repo = secret_repo

    async def handle(self, trigger: Trigger) -> Session | None:
        with TemporaryDirectory() as cloned_repo:
            return await self._handle(Path(cloned_repo), trigger)

    async def _handle(
        self, cloned_repo: Path, trigger: Trigger
    ) -> Session | None:
        trigger.env = self.get_env_vars(trigger)
        trigger.secret = self.get_secrets(trigger)

        files = await self.gather_workflows(trigger, cloned_repo)

        if not files:
            return None

        # TODO: allow for multiple workflows in one session
        assert len(files) == 1

        session_id = uuid4()

        filenode = files[0]

        title = eval_title(filenode.title)

        match filenode:
            case FileNode(run_on=RunOnStatement(type=RunType.SELF_HOSTED)):
                status = SessionStatus.BOOTING
                run_on_self_hosted = True

            case _:
                status = SessionStatus.PENDING
                run_on_self_hosted = False

        session = Session(
            id=session_id,
            trigger=trigger,
            status=status,
            run_on_self_hosted=run_on_self_hosted,
            # TODO: move to workflow object
            title=title,
        )
        self.session_repo.create(session)

        def callback(data: bytes) -> None:  # pragma: no cover
            self.terminal_session_repo.append_to_session(session_id, data)

        terminal = self.terminal_session_repo.create(session_id)
        terminal.callback = callback

        try:
            await self.workflow_runner(
                session, terminal, cloned_repo, filenode
            )

        except Exception:
            logger = logging.getLogger("cicada")
            logger.exception("Workflow crashed:")

            session.finish(SessionStatus.FAILURE)

        assert session.status != SessionStatus.PENDING
        assert session.finished_at is not None

        self.session_repo.update(session)

        return self.session_repo.get_session_by_session_id(
            session.id,
            session.run,
        )

    def get_env_vars(self, trigger: Trigger) -> dict[str, str]:
        return get_env_vars_for_repo(
            self.env_repo, self.repository_repo, trigger
        )

    def get_secrets(self, trigger: Trigger) -> dict[str, str]:
        cmd = GatherSecretsFromTrigger(
            self.repository_repo, self.installation_repo, self.secret_repo
        )

        return cmd.handle(trigger)
