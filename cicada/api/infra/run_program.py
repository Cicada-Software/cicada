import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, nullcontext
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import ClassVar

from cicada.ast.generate import AstError
from cicada.ast.nodes import FileNode, RunType
from cicada.domain.repo.runner_repo import IRunnerRepo
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.session import Session, SessionStatus, Workflow, WorkflowStatus
from cicada.domain.terminal_session import TerminalIsFinished, TerminalSession
from cicada.domain.triggers import Trigger
from cicada.eval.constexpr_visitor import WorkflowFailure
from cicada.eval.container import RemoteContainerEvalVisitor

logger = logging.getLogger("cicada")


EXIT_CODE_MAPPINGS = {
    -1: SessionStatus.STOPPED,
    0: SessionStatus.SUCCESS,
}


def exit_code_to_status_code(exit_code: int) -> SessionStatus:
    return EXIT_CODE_MAPPINGS.get(exit_code, SessionStatus.FAILURE)


@dataclass
class ExecutionContext:
    trigger: Trigger
    terminal: TerminalSession
    cloned_repo: Path
    workflow: Workflow

    async def run(self, file: FileNode) -> int:
        raise NotImplementedError


@dataclass
class RemoteDockerLikeExecutionContext(ExecutionContext):
    """
    Inject commands into a running container as opposed to running a container
    directly. The above solutions require that Cicada is installed in the
    container along side the cloned repository, but means you are unable to
    bring your own container. With the remote container though you can (in
    theory) specify whatever container you want, and Cicada will inject the
    commands into the container.

    This is the base for both Docker and Podman remote executors since they are
    similar.
    """

    program: ClassVar[str]
    executor_name: ClassVar[str]

    sub_workflows: asyncio.Queue[
        tuple[RemoteContainerEvalVisitor, Workflow, Awaitable[None]]
    ] = field(default_factory=asyncio.Queue, init=False)
    get_wrapper_for_trigger_type: Callable[
        [Session, Workflow], AbstractAsyncContextManager[None]
    ] | None = field(default=None, init=False)
    session_repo: ISessionRepo = field(init=False)
    terminal_repo: ITerminalSessionRepo = field(init=False)
    session: Session = field(init=False)

    async def run(self, file: FileNode) -> int:
        if not await self.is_program_installed():
            msg = f"Cannot use `{self.executor_name}` executor because {self.program} is not installed!"  # noqa: E501

            logger.error(msg)

            return 1

        assert file.file

        tg = asyncio.TaskGroup()

        listener = asyncio.create_task(
            self.listen_for_sub_workflows(self.session_repo, tg, self.session)
        )

        async with tg:
            exit_code = await tg.create_task(self.run_file(file))

            self.workflow.finish(exit_code_to_status_code(exit_code))

        listener.cancel()

        return exit_code

    async def run_file(self, tree: FileNode) -> int:
        image = "ghcr.io/cicada-software/cicada-executor:latest"

        if tree.run_on and tree.run_on.type == RunType.IMAGE:
            image = tree.run_on.value

        if ":" not in image:
            image += ":latest"

        visitor: RemoteContainerEvalVisitor | None = None

        try:
            visitor = RemoteContainerEvalVisitor(
                self.cloned_repo,
                self.trigger,
                self.terminal,
                image=image,
                program=self.program,
                workflow=self.workflow,
                sub_workflows=self.sub_workflows,
            )
            await visitor.setup()

            await tree.accept(visitor)

        except WorkflowFailure as exc:
            return exc.return_code

        except TerminalIsFinished:
            return 1

        finally:
            if visitor:
                await visitor.cleanup()

        return 0

    async def is_program_installed(self) -> bool:
        proc = await asyncio.create_subprocess_shell(
            f"{self.program} --version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        await proc.wait()

        return proc.returncode == 0

    async def listen_for_sub_workflows(
        self,
        session_repo: ISessionRepo,
        tg: asyncio.TaskGroup,
        session: Session,
    ) -> None:
        async def run(sub_workflow: Workflow, runner: Awaitable[None]) -> None:
            if self.get_wrapper_for_trigger_type:
                wrapper = self.get_wrapper_for_trigger_type(session, sub_workflow)

            else:
                wrapper = nullcontext()

            async with wrapper:
                try:
                    await runner

                    sub_workflow.finish(WorkflowStatus.SUCCESS)

                except Exception:
                    sub_workflow.finish(WorkflowStatus.FAILURE)

                    raise

                finally:
                    session_repo.update_workflow(sub_workflow)

        while True:
            visitor, sub_workflow, runner = await self.sub_workflows.get()
            self.sub_workflows.task_done()

            session_repo.create_workflow(sub_workflow, session)
            visitor.terminal = self.terminal_repo.create(sub_workflow.id)
            visitor.terminal.callback = partial(
                self.terminal_repo.append_to_workflow, sub_workflow.id
            )

            tg.create_task(run(sub_workflow, runner))


class RemotePodmanExecutionContext(RemoteDockerLikeExecutionContext):
    program = "podman"
    executor_name = "remote-podman"


class RemoteDockerExecutionContext(RemoteDockerLikeExecutionContext):
    program = "docker"
    executor_name = "remote-docker"


@dataclass
class SelfHostedExecutionContext(ExecutionContext):
    """
    This is an executor that facilitates communication with a self-hosted
    runner. Each workflow that needs to be ran is added to the runner queue,
    and when a runner connects to the runner websocket, the data is popped
    off the queue and handled. While we wait for the runner to start the job
    we continually check the status of the session to see if it has finished
    or not. Once all the workflows are finished we exit, and the session is
    finished.
    """

    url: str
    session: Session
    session_repo: ISessionRepo
    runner_repo: IRunnerRepo

    async def run(self, file: FileNode) -> int:
        assert file.file

        session_status: SessionStatus | None = None

        try:
            self.runner_repo.queue_session(self.session, file, self.url)

            while True:
                # TODO: make specialized function to just get status
                session = self.session_repo.get_session_by_session_id(
                    self.session.id,
                    run=self.session.run,
                )
                assert session

                session_status = session.status

                if session_status.is_finished():
                    break

                await asyncio.sleep(1)

        except AstError:
            # Shouldn't happen, gather phase should pass without issues

            logging.getLogger("cicada").exception("")

            return 1

        # TODO: don't turn session status into int since it just gets
        # converted back to a session status anyways
        return 1 if not session or session_status.is_failure() else 0


EXECUTOR_MAPPING = {
    RemotePodmanExecutionContext.executor_name: RemotePodmanExecutionContext,
    RemoteDockerExecutionContext.executor_name: RemoteDockerExecutionContext,
}


def get_execution_type(name: str) -> type[ExecutionContext]:
    return EXECUTOR_MAPPING[name]
