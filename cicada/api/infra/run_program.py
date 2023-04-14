import json
from asyncio import create_subprocess_exec, create_task, subprocess
from dataclasses import dataclass
from typing import Any

from cicada.api.domain.session import SessionStatus
from cicada.api.domain.terminal_session import TerminalSession
from cicada.api.domain.triggers import TriggerType


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

    except Exception as ex:
        terminal.finish()

        if process:
            process.kill()

        raise ex


EXIT_CODE_MAPPINGS = {
    -1: SessionStatus.STOPPED,
    0: SessionStatus.SUCCESS,
}


def exit_code_to_status_code(exit_code: int) -> SessionStatus:
    return EXIT_CODE_MAPPINGS.get(exit_code, SessionStatus.FAILURE)


@dataclass
class ExecutionContext:  # type: ignore
    url: str
    trigger_type: TriggerType
    trigger: dict[str, Any]  # type: ignore
    terminal: TerminalSession
    env: dict[str, str]


async def run_docker_workflow(ctx: ExecutionContext) -> int:
    return await run_program(
        [
            "docker",
            "run",
            "-e",
            f"CLONE_URL={ctx.url}",
            "-e",
            f"CICADA_TRIGGER={json.dumps(ctx.trigger, separators=(',', ':'))}",
            "--rm",
            "-t",
            "cicada",
        ],
        ctx.terminal,
    )
