import asyncio
import json
from asyncio import create_subprocess_exec, create_task, subprocess
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from cicada.api.common.json import asjson
from cicada.api.domain.session import SessionStatus
from cicada.api.domain.terminal_session import TerminalSession
from cicada.api.domain.triggers import Trigger, TriggerType
from cicada.ast.generate import AstError, generate_ast_tree
from cicada.ast.nodes import RunType
from cicada.ast.semantic_analysis import SemanticAnalysisVisitor
from cicada.eval.container import CommandFailed, RemoteContainerEvalVisitor
from cicada.eval.find_files import find_ci_files
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
                terminal.handle_line(line.decode())

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
    trigger_type: TriggerType
    trigger: Trigger
    terminal: TerminalSession
    cloned_repo: Path

    async def run(self) -> int:
        raise NotImplementedError()


class DockerExecutionContext(ExecutionContext):
    async def run(self) -> int:
        trigger = json.dumps(asjson(self.trigger), separators=(",", ":"))

        return await run_program(
            [
                "docker",
                "run",
                "-e",
                f"CLONE_URL={self.url}",
                "-e",
                f"CICADA_TRIGGER={trigger}",
                "--rm",
                "-t",
                "cicada",
            ],
            self.terminal,
        )


class PodmanExecutionContext(ExecutionContext):
    async def run(self) -> int:
        trigger = json.dumps(asjson(self.trigger), separators=(",", ":"))

        return await run_program(
            [
                "podman",
                "run",
                "-e",
                f"CLONE_URL={self.url}",
                "-e",
                f"CICADA_TRIGGER={trigger}",
                "--rm",
                "-t",
                "cicada",
            ],
            self.terminal,
        )


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
        for file in find_ci_files(self.cloned_repo):
            return await asyncio.to_thread(partial(self.run_file, file))

        assert False, "Expected at least one workflow"

    def run_file(self, file: Path) -> int:
        try:
            tokens = tokenize(file.read_text())
            tree = generate_ast_tree(tokens)

            semantics = SemanticAnalysisVisitor(self.trigger)
            tree.accept(semantics)

        except AstError as exc:
            # Shouldn't happen, gather phase should pass without issues
            print(exc)

            return 1

        image = "alpine"

        if semantics.run_on and semantics.run_on.type == RunType.IMAGE:
            image = semantics.run_on.value

        visitor = RemoteContainerEvalVisitor(
            self.cloned_repo,
            self.trigger,
            self.terminal,
            image=image,
        )

        try:
            tree.accept(visitor)

        except CommandFailed as exc:
            return exc.return_code

        finally:
            visitor.cleanup()

        return 0


EXECUTOR_MAPPING = {
    "docker": DockerExecutionContext,
    "podman": PodmanExecutionContext,
    "remote-podman": RemotePodmanExecutionContext,
}


def get_execution_type(name: str) -> type[ExecutionContext]:
    return EXECUTOR_MAPPING[name]
