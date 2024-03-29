import asyncio
import logging
import shutil
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

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
from cicada.eval.constexpr_visitor import eval_title


# TODO: rename to some thing more fitting
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

    async def handle(self, trigger: Trigger) -> list[Session]:
        self.trigger = trigger

        with TemporaryDirectory() as cloned_repo:
            self.cloned_repo = Path(cloned_repo)

            self._inject_env_vars_and_secrets_into_trigger()

            workflows = await self.gather_workflows(self.trigger, self.cloned_repo)

            # TODO: limit max concurrent workflows
            return await asyncio.gather(*[self.copy_and_run(x) for x in workflows])

    async def copy_and_run(self, filenode: FileNode) -> Session:
        """
        Create a fresh copy of the cloned repository and run a workflow from the new directory so
        that each workflow has an isolated copy of the repository.
        """

        with TemporaryDirectory() as dir:
            copy = Path(dir)

            shutil.copytree(self.cloned_repo, copy, dirs_exist_ok=True)

            assert filenode.file
            filenode.file = copy / filenode.file.relative_to(self.cloned_repo)

            return await self.run_workflow(filenode, copy)

    async def run_workflow(self, filenode: FileNode, dir: Path) -> Session:
        status, run_on_self_hosted = self._get_boot_info(filenode)

        session = Session(id=uuid4(), trigger=self.trigger, status=status)
        self.session_repo.create(session)

        assert filenode.file

        workflow = Workflow.from_session(
            session,
            filename=filenode.file.relative_to(dir),
            run_on_self_hosted=run_on_self_hosted,
            title=await eval_title(filenode.title),
        )
        self.session_repo.create_workflow(workflow, session)

        terminal = self.terminal_session_repo.create(workflow.id)
        terminal.callback = partial(self.terminal_session_repo.append_to_workflow, workflow.id)

        try:
            await self.workflow_runner(session, terminal, dir, filenode, workflow)

        except Exception:
            logger = logging.getLogger("cicada")
            logger.exception("Workflow crashed:")

            # TODO: find and cleanup orphaned workflows instead of assuming root workflow failed
            workflow.finish(SessionStatus.FAILURE)

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

    def _inject_env_vars_and_secrets_into_trigger(self) -> None:
        self.trigger.env = self._get_env_vars()
        self.trigger.secret = self._get_secrets()

    def _get_env_vars(self) -> dict[str, str]:
        return get_env_vars_for_repo(self.env_repo, self.repository_repo, self.trigger)

    def _get_secrets(self) -> dict[str, str]:
        cmd = GatherSecretsFromTrigger(
            self.repository_repo, self.installation_repo, self.secret_repo
        )

        return cmd.handle(self.trigger)

    @staticmethod
    def _get_boot_info(filenode: FileNode) -> tuple[SessionStatus, bool]:
        match filenode:
            case FileNode(run_on=RunOnStatement(type=RunType.SELF_HOSTED)):
                status = SessionStatus.BOOTING
                run_on_self_hosted = True

            case _:
                status = SessionStatus.PENDING
                run_on_self_hosted = False

        return status, run_on_self_hosted
