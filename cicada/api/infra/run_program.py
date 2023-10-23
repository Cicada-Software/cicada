import asyncio
import logging
from asyncio import create_subprocess_exec, create_task, subprocess
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from cicada.ast.generate import AstError, generate_ast_tree
from cicada.ast.nodes import FileNode, RunType
from cicada.ast.semantic_analysis import SemanticAnalysisVisitor
from cicada.domain.repo.runner_repo import IRunnerRepo
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.session import Session, SessionStatus
from cicada.domain.terminal_session import TerminalIsFinished, TerminalSession
from cicada.eval.constexpr_visitor import WorkflowFailure
from cicada.eval.container import RemoteContainerEvalVisitor
from cicada.parse.tokenize import tokenize

logger = logging.getLogger("cicada")


async def process_killer(process: subprocess.Process, terminal: TerminalSession) -> None:
    """If terminal session is killed, kill process."""

    await terminal.should_stop.wait()
    process.kill()


async def run_program(args: list[str], terminal: TerminalSession) -> int:
    """
    Run a program passed specified via `args`, and print output to `terminal`.
    Return the exit code of the process, or -1 if the process was stopped by
    the user.
    """

    process: subprocess.Process | None = None

    try:
        process = await create_subprocess_exec(*args, stdout=subprocess.PIPE)

        killer = create_task(process_killer(process, terminal))

        while True:
            if not process.stdout:
                break  # pragma: no cover

            line = await process.stdout.readline()

            if line:
                terminal.append(line)

            if not line or terminal.should_stop.is_set():
                break

        terminal.finish()
        killer.cancel()
        await process.wait()

        # TODO: return SessionStatus instead of exit code?
        return -1 if terminal.should_stop.is_set() else process.returncode or 0

    except Exception:
        terminal.finish()

        if process:
            process.kill()

        raise


EXIT_CODE_MAPPINGS = {
    -1: SessionStatus.STOPPED,
    0: SessionStatus.SUCCESS,
}


def exit_code_to_status_code(exit_code: int) -> SessionStatus:
    return EXIT_CODE_MAPPINGS.get(exit_code, SessionStatus.FAILURE)


@dataclass
class ExecutionContext:
    url: str
    session: Session
    terminal: TerminalSession
    cloned_repo: Path

    async def run(self, file: FileNode) -> int:
        raise NotImplementedError


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

    program: str
    executor_name: str

    async def run(self, file: FileNode) -> int:
        if not await self.is_program_installed():
            msg = f"Cannot use `{self.executor_name}` executor because {self.program} is not installed!"  # noqa: E501

            logger.error(msg)

            # TODO: move terminal cleanup out of visitor
            self.terminal.finish()

            return 1

        assert file.file

        return await asyncio.to_thread(partial(self.run_file, file.file))

    def run_file(self, file: Path) -> int:
        try:
            tokens = tokenize(file.read_text())
            tree = generate_ast_tree(tokens)

            semantics = SemanticAnalysisVisitor(self.session.trigger)
            tree.accept(semantics)

        except AstError as exc:
            # Shouldn't happen, gather phase should pass without issues

            logging.getLogger("cicada").exception(exc)

            return 1

        image = "ghcr.io/cicada-software/cicada-executor:latest"

        if semantics.run_on and semantics.run_on.type == RunType.IMAGE:
            image = semantics.run_on.value

        if ":" not in image:
            image += ":latest"

        visitor: RemoteContainerEvalVisitor | None = None

        try:
            visitor = RemoteContainerEvalVisitor(
                self.cloned_repo,
                self.session,
                self.terminal,
                image=image,
                program=self.program,
            )

            tree.accept(visitor)

        except WorkflowFailure as exc:
            return exc.return_code

        except TerminalIsFinished:
            return 1

        finally:
            if visitor:
                visitor.cleanup()

        return 0

    async def is_program_installed(self) -> bool:
        proc = await asyncio.create_subprocess_shell(
            f"{self.program} --version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        await proc.wait()

        return proc.returncode == 0


class RemotePodmanExecutionContext(RemoteDockerLikeExecutionContext):
    program = "podman"
    executor_name = "remote-podman"


class RemoteDockerExecutionContext(RemoteDockerLikeExecutionContext):
    program = "docker"
    executor_name = "remote-docker"


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

        finally:
            self.terminal.finish()

        # TODO: don't turn session status into int since it just gets
        # converted back to a session status anyways
        return 1 if not session or session_status.is_failure() else 0


EXECUTOR_MAPPING = {
    RemotePodmanExecutionContext.executor_name: RemotePodmanExecutionContext,
    RemoteDockerExecutionContext.executor_name: RemoteDockerExecutionContext,
}


def get_execution_type(name: str) -> type[ExecutionContext]:
    return EXECUTOR_MAPPING[name]
