from __future__ import annotations

import shlex
import subprocess
from subprocess import PIPE, STDOUT, CompletedProcess
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cicada.ast.nodes import FunctionExpression, RecordValue, Value
from cicada.ast.types import RecordType
from cicada.eval.constexpr_visitor import ConstexprEvalVisitor
from cicada.eval.main import to_string

if TYPE_CHECKING:
    from pathlib import Path

    from cicada.api.domain.terminal_session import TerminalSession
    from cicada.api.domain.triggers import Trigger


class CommandFailed(ValueError):
    def __init__(self, return_code: int) -> None:
        self.return_code = return_code


class RemoteContainerEvalVisitor(ConstexprEvalVisitor):  # pragma: no cover
    pod_label: UUID
    container_id: str
    terminal: TerminalSession
    cloned_repo: Path

    def __init__(
        self,
        cloned_repo: Path,
        trigger: Trigger,
        terminal: TerminalSession,
    ) -> None:
        super().__init__(trigger)

        self.terminal = terminal
        self.cloned_repo = cloned_repo

        self.pod_id = uuid4()

        self._start_pod()

    def cleanup(self) -> None:
        self.terminal.finish()

        subprocess.run(
            ["podman", "kill", self.container_id],
            stdout=PIPE,
            stderr=STDOUT,
        )

    def visit_func_expr(self, node: FunctionExpression) -> Value:
        if node.name == "shell":
            args: list[str] = []

            for arg in node.args:
                args.append(to_string(arg.accept(self)))

            args = [shlex.quote(arg) for arg in args]

            process = self._pod_exec(args)

            self.terminal.handle_line(process.stdout.decode())

            if process.returncode != 0:
                raise CommandFailed(process.returncode)

        return RecordValue({}, RecordType())

    def _start_pod(self) -> None:
        # TODO: add timeout
        process = subprocess.run(
            [
                "podman",
                "run",
                "--rm",
                "--detach",
                "--mount",
                f"type=bind,src={self.cloned_repo},dst={self.temp_dir}",
                "alpine",
                "sleep",
                "infinity",
            ],
            stdout=PIPE,
            stderr=STDOUT,
        )

        if process.returncode != 0:
            raise ValueError("Could not start container")

        self.container_id = process.stdout.decode().strip()

    def _pod_exec(self, args: list[str]) -> CompletedProcess[bytes]:
        # This command is a hack to make sure we are in cwd from the last
        # command that was ran. Because each `exec` command is executed in the
        # container WORKDIR folder the cwd is not saved after `exec` finishes.
        # To fix this we attempt to cd into the saved directory, run the
        # command, then save the cwd for the next command. We also keep track
        # of the exit code so that we can return it after saving the cwd.
        cmd = " ; ".join(
            [
                f'cd "$(cat /tmp/__cicada_cwd 2> /dev/null || echo "{self.temp_dir}")"',  # noqa: E501
                " ".join(args),
                '__cicada_exit_code="$?"',
                'echo "$PWD" > /tmp/__cicada_cwd',
                'exit "$__cicada_exit_code"',
            ]
        )

        return subprocess.run(
            [
                "podman",
                "exec",
                self.container_id,
                "/bin/sh",
                "-c",
                cmd,
            ],
            stdout=PIPE,
            stderr=STDOUT,
        )

    @property
    def temp_dir(self) -> str:
        return f"/tmp/{self.pod_id}"
