from __future__ import annotations

import os
import pty
import shlex
import subprocess
import sys
import termios
from contextlib import suppress
from itertools import chain
from subprocess import PIPE, STDOUT
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cicada.ast.nodes import (
    FunctionExpression,
    RecordValue,
    StringValue,
    UnitValue,
    Value,
)
from cicada.ast.types import RecordType
from cicada.domain.triggers import CommitTrigger
from cicada.eval.constexpr_visitor import (
    CommandFailed,
    ConstexprEvalVisitor,
    WorkflowFailure,
)

if TYPE_CHECKING:
    from pathlib import Path

    from cicada.domain.terminal_session import TerminalSession
    from cicada.domain.triggers import Trigger


class ContainerTermination(WorkflowFailure):
    pass


class RemoteContainerEvalVisitor(ConstexprEvalVisitor):  # pragma: no cover
    pod_label: UUID
    container_id: str
    terminal: TerminalSession
    cloned_repo: Path

    max_columns: int = 120

    def __init__(
        self,
        cloned_repo: Path,
        trigger: Trigger,
        terminal: TerminalSession,
        image: str,
    ) -> None:
        super().__init__(trigger)

        self.terminal = terminal
        self.cloned_repo = cloned_repo

        self.pod_id = uuid4()

        self._start_pod(image)

    def cleanup(self) -> None:
        self.terminal.finish()

        subprocess.run(
            ["podman", "kill", self.container_id],
            stdout=PIPE,
            stderr=STDOUT,
        )

    def visit_func_expr(self, node: FunctionExpression) -> Value:
        args: list[str] = []

        for arg in node.args:
            value = arg.accept(self)

            assert isinstance(value, StringValue)

            args.append(value.value)

        if node.name == "shell":
            exit_code = self._pod_exec(args)

            if exit_code != 0:
                raise CommandFailed(exit_code)

            return RecordValue({}, RecordType())

        if node.name == "print":
            self.terminal.append(" ".join(args).encode())

        return UnitValue()

    def _start_pod(self, image: str) -> None:
        # TODO: add timeout
        process = subprocess.run(
            [
                "podman",
                "run",
                "--rm",
                "--detach",
                "--entrypoint",
                '["sleep","infinity"]',
                "--mount",
                f"type=bind,src={self.cloned_repo},dst={self.temp_dir}",
                image,
            ],
            stdout=PIPE,
            stderr=STDOUT,
        )

        if process.returncode != 0:
            msg = f"Could not start container. Make sure image `{image}` exists and is valid, then retry."  # noqa: E501

            self.terminal.append(msg.encode())
            self.terminal.finish()

            raise ContainerTermination(1)

        self.container_id = (
            process.stdout.strip().split(b"\n")[-1].decode().strip()
        )

    def _pod_exec(self, args: list[str]) -> int:
        # This command is a hack to make sure we are in cwd from the last
        # command that was ran. Because each `exec` command is executed in the
        # container WORKDIR folder the cwd is not saved after `exec` finishes.
        # To fix this we attempt to cd into the saved directory, run the
        # command, then save the cwd for the next command. We also keep track
        # of the exit code so that we can return it after saving the cwd.
        cmd = " ; ".join(
            [
                f'cd "$(cat /tmp/__cicada_cwd 2> /dev/null || echo "{self.temp_dir}")"',  # noqa: E501
                shlex.join(args),
                '__cicada_exit_code="$?"',
                'echo "$PWD" > /tmp/__cicada_cwd',
                'exit "$__cicada_exit_code"',
            ]
        )

        # Hacky tty magic from: https://stackoverflow.com/a/28925318
        master, slave = pty.openpty()

        with suppress(termios.error):
            # Attempt to set TTY to desired max_column size. This might fail,
            # so we suppress the error. This is probably due to the terminal
            # not supporting the ability to resize the terminal.
            lines, _ = termios.tcgetwinsize(sys.stdout)
            termios.tcsetwinsize(sys.stdout, (lines, self.max_columns))

        assert self.trigger, "impossible"

        env_vars = [
            *get_provider_default_env_vars(self.trigger),
            *get_env_vars_from_trigger(self.trigger),
        ]

        # Add "-e" flag before each env var
        extra_args = chain.from_iterable(["-e", x] for x in env_vars)

        process = subprocess.Popen(
            [
                "podman",
                "exec",
                "-e",
                f"COLUMNS={self.max_columns}",
                *extra_args,
                "-t",
                # TODO: Fix GitHub Codespaces emitting warnings
                "--log-level=error",
                self.container_id,
                "/bin/sh",
                "-c",
                cmd,
            ],
            stdout=slave,
            stderr=STDOUT,
            close_fds=True,
        )

        os.close(slave)

        with suppress(IOError):
            while True:
                data = os.read(master, 1024)

                if not data:
                    break

                self.terminal.append(data)

        return process.wait()

    @property
    def temp_dir(self) -> str:
        return f"/tmp/{self.pod_id}"


def get_provider_default_env_vars(trigger: Trigger) -> list[str]:
    # TODO: add gitlab equivalent arg names

    args = ["CI=true", f"GITHUB_SHA={trigger.sha}"]

    # TODO: add to all triggers
    if isinstance(trigger, CommitTrigger):
        args.extend(
            [
                f"GITHUB_REF={shlex.quote(trigger.ref)}",
                f"GITHUB_REF_NAME={shlex.quote(trigger.branch)}",
            ]
        )

    return args


def get_env_vars_from_trigger(trigger: Trigger) -> list[str]:
    return [
        f"{shlex.quote(k)}={shlex.quote(v)}" for k, v in trigger.env.items()
    ]
