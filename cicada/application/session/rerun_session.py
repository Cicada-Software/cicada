import logging
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

from cicada.application.secret.gather_secrets_from_trigger import GatherSecretsFromTrigger
from cicada.application.session.common import IWorkflowGatherer, IWorkflowRunner
from cicada.ast.nodes import FileNode, RunOnStatement, RunType
from cicada.domain.repo.environment_repo import IEnvironmentRepo
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.services.repository import get_env_vars_for_repo
from cicada.domain.session import Session, SessionStatus, Workflow, WorkflowStatus
from cicada.domain.triggers import Trigger


class RerunSession:
    """
    This service is very similar to the MakeSessionFromTrigger service, except
    that this service simply re-runs the most recent run for a session instead
    of creating a new session from a trigger.

    All arguments to this service are the same as the MakeSessionFromTrigger
    service. The only difference between these services is that the handle()
    method takes a session object, and a new session with the same ID is
    created, except the `run` number is incremented by 1.

    One edge case with this service is that if no workflow files are found when
    running the gather step, the session will not re-run. Since we know the SHA
    that the session was ran at, we might not need even run the gather stage,
    but for now this is how it is executing.
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

    async def handle(self, session: Session) -> Session | None:
        with TemporaryDirectory() as cloned_repo:
            return await self._handle(Path(cloned_repo), session)

    async def _handle(self, cloned_repo: Path, session: Session) -> Session | None:
        session.trigger.env = self.get_env_vars(session.trigger)
        session.trigger.secret = self.get_secrets(session.trigger)

        # TODO: assert previous session(s) arent pending
        files = await self.gather_workflows(session.trigger, cloned_repo)

        if not files:
            return None

        filenode = files[0]

        # TODO: isolate this logic (shared with MakeSessionFromTrigger service)
        match filenode:
            case FileNode(run_on=RunOnStatement(type=RunType.SELF_HOSTED)):
                status = SessionStatus.BOOTING
                run_on_self_hosted = True

            case _:
                status = SessionStatus.PENDING
                run_on_self_hosted = False

        old_session = session

        session = Session(
            id=session.id,
            status=status,
            trigger=session.trigger,
            run=session.run + 1,
        )
        self.session_repo.create(session)

        assert filenode.file

        workflow = Workflow.from_session(
            session,
            filename=filenode.file.relative_to(cloned_repo),
            run_on_self_hosted=run_on_self_hosted,
            title=self._get_old_workflow_title(old_session),
        )
        self.session_repo.create_workflow(workflow, session)

        terminal = self.terminal_session_repo.create(workflow.id)
        terminal.callback = partial(self.terminal_session_repo.append_to_workflow, workflow.id)

        try:
            await self.workflow_runner(session, terminal, cloned_repo, filenode, workflow)

        except Exception:
            logger = logging.getLogger("cicada")
            logger.exception("Workflow crashed:")

            workflow.finish(WorkflowStatus.FAILURE)

        terminal.finish()

        assert workflow.status != WorkflowStatus.PENDING
        assert workflow.finished_at is not None

        self.session_repo.update_workflow(workflow)

        session_with_workflows = self.session_repo.get_session_by_session_id(
            session.id, session.run
        )
        assert session_with_workflows

        session_with_workflows.finish()
        self.session_repo.update(session_with_workflows)

        return session_with_workflows

    def get_env_vars(self, trigger: Trigger) -> dict[str, str]:
        return get_env_vars_for_repo(self.env_repo, self.repository_repo, trigger)

    def get_secrets(self, trigger: Trigger) -> dict[str, str]:
        cmd = GatherSecretsFromTrigger(
            self.repository_repo,
            self.installation_repo,
            self.secret_repo,
        )

        return cmd.handle(trigger)

    def _get_old_workflow_title(self, session: Session) -> str | None:
        # TODO: remove/rename this function after session/workflow terminology is ironed out

        workflow_id = self.session_repo.get_workflow_id_from_session(session)

        if not workflow_id:
            return None

        workflow = self.session_repo.get_workflow_by_id(workflow_id)

        if not workflow:
            return None

        return workflow.title
