import asyncio
import logging
from asyncio import create_subprocess_exec, create_task, subprocess
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from cicada.api.infra.repo_get_ci_files import folder_get_runnable_ci_files
from cicada.ast.generate import AstError, generate_ast_tree
from cicada.ast.nodes import RunType
from cicada.ast.semantic_analysis import SemanticAnalysisVisitor
from cicada.domain.repo.runner_repo import IRunnerRepo
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.session import Session, SessionStatus
from cicada.domain.terminal_session import TerminalSession
from cicada.domain.triggers import Trigger, TriggerType
from cicada.eval.constexpr_visitor import WorkflowFailure
from cicada.eval.container import RemoteContainerEvalVisitor
from cicada.parse.tokenize import tokenize


async def process_killer(
    process: subprocess.Process, terminal: TerminalSession
) -> None:
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
    # TODO: dont include these, they can be pulled from session
    trigger_type: TriggerType
    trigger: Trigger
    session: Session
    terminal: TerminalSession
    cloned_repo: Path

    async def run(self) -> int:
        raise NotImplementedError()


class RemotePodmanExecutionContext(ExecutionContext):
    """
    Inject commands into a running container as opposed to running a container
    directly. The above solutions require that Cicada is installed in the
    container along side the cloned repository, but means you are unable to
    bring your own container. With the remote container though you can (in
    theory) specify whatever container you want, and Cicada will inject the
    commands into the container.
    """

    async def run(self) -> int:
        files = folder_get_runnable_ci_files(self.cloned_repo, self.trigger)

        for file in files:
            if isinstance(file, AstError):
                # TODO: handle this
                continue

            assert file.file

            return await asyncio.to_thread(partial(self.run_file, file.file))

        assert False, "Expected at least one workflow"

    def run_file(self, file: Path) -> int:
        try:
            tokens = tokenize(file.read_text())
            tree = generate_ast_tree(tokens)

            semantics = SemanticAnalysisVisitor(self.trigger)
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
                self.trigger,
                self.terminal,
                image=image,
            )

            tree.accept(visitor)

        except WorkflowFailure as exc:
            return exc.return_code

        finally:
            if visitor:
                visitor.cleanup()

        return 0


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

    async def run(self) -> int:
        files = folder_get_runnable_ci_files(self.cloned_repo, self.trigger)

        for file in files:
            if isinstance(file, AstError):
                continue

            assert file.file

            try:
                self.runner_repo.queue_session(self.session, file, self.url)

                while True:
                    # TODO: make specialized function to just get status
                    session = self.session_repo.get_session_by_session_id(
                        self.session.id,
                        run=self.session.run,
                    )
                    assert session

                    if session.status.is_finished():
                        break

                    await asyncio.sleep(1)

            except AstError:
                # Shouldn't happen, gather phase should pass without issues

                logging.getLogger("cicada").exception("")

                return 1

            self.terminal.finish()

            return 0

        assert False, "Expected at least one workflow"


EXECUTOR_MAPPING = {
    "remote-podman": RemotePodmanExecutionContext,
}


def get_execution_type(name: str) -> type[ExecutionContext]:
    return EXECUTOR_MAPPING[name]
