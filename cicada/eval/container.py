from __future__ import annotations

import logging
import os
import pty
import shlex
import subprocess
import sys
import termios
from contextlib import suppress
from itertools import chain
from pathlib import Path
from subprocess import PIPE, STDOUT
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from cicada.api.infra.cache_repo import CacheRepo
from cicada.application.cache.cache_files import CacheFilesForSession
from cicada.application.cache.restore_cache import RestoreCache
from cicada.ast.generate import SHELL_ALIASES
from cicada.ast.nodes import (
    CacheStatement,
    FileNode,
    FunctionDefStatement,
    FunctionExpression,
    FunctionValue,
    IdentifierExpression,
    RecordValue,
    StringValue,
    UnitValue,
    UnreachableValue,
    Value,
)
from cicada.ast.semantic_analysis import StringCoercibleType
from cicada.ast.types import (
    FunctionType,
    RecordType,
    StringType,
    UnitType,
    VariadicTypeArg,
)
from cicada.domain.cache import CacheKey
from cicada.domain.triggers import CommitTrigger
from cicada.eval.constexpr_visitor import (
    CommandFailed,
    ConstexprEvalVisitor,
    WorkflowFailure,
)

if TYPE_CHECKING:
    from cicada.domain.session import Session
    from cicada.domain.terminal_session import TerminalSession
    from cicada.domain.triggers import Trigger


class ContainerTermination(WorkflowFailure):
    pass


class RemoteContainerEvalVisitor(ConstexprEvalVisitor):  # pragma: no cover
    session: Session

    container_id: str
    terminal: TerminalSession
    cloned_repo: Path

    # Program used to run container (ie, docker or podman)
    program: str

    max_columns: int = 120

    # TODO: isolate this logic in consteval visitor (or a visitor that estends
    # from it.
    cached_files: list[Path] | None
    cache_key: str | None

    def __init__(
        self,
        cloned_repo: Path,
        session: Session,
        terminal: TerminalSession,
        image: str,
        program: str,
    ) -> None:
        super().__init__(session.trigger)

        self.session = session

        self.terminal = terminal
        self.cloned_repo = cloned_repo

        self.uuid = uuid4()
        self.program = program

        self.cached_files = None
        self.cache_key = None

        # TODO: deduplicate this monstrosity
        built_in_symbols = {
            "shell": FunctionValue(
                type=FunctionType(
                    [VariadicTypeArg(StringCoercibleType)], rtype=RecordType()
                ),
                func=self.builtin_shell,
            ),
            "print": FunctionValue(
                FunctionType(
                    [VariadicTypeArg(StringCoercibleType)],
                    rtype=UnitType(),
                ),
                func=self.builtin_print,
            ),
            "hashOf": FunctionValue(
                FunctionType(
                    [StringType(), VariadicTypeArg(StringType())],
                    rtype=StringType(),
                ),
                func=self.hashOf,
            ),
            **{
                alias: FunctionValue(
                    FunctionType([StringCoercibleType], rtype=RecordType()),
                    func=self.builtin_shell,
                )
                for alias in SHELL_ALIASES
            },
        }

        self.symbols.update(built_in_symbols)

        self._start_container(image)

    def cleanup(self) -> None:
        self.terminal.finish()

        process = subprocess.run(  # noqa: PLW1510
            [self.program, "kill", self.container_id],
            stdout=PIPE,
            stderr=STDOUT,
        )

        if process.returncode != 0:
            logging.getLogger("cicada").error(
                f"Could not kill container id: {self.container_id}"
            )

    def visit_file_node(self, node: FileNode) -> Value:
        output = super().visit_file_node(node)

        if (
            isinstance(output, UnitValue)
            and self.cached_files
            and self.cache_key
            and self.trigger
        ):
            cmd = CacheFilesForSession(CacheRepo())
            cmd.handle(
                self.cached_files,
                CacheKey(self.cache_key),
                self.session,
                self.cloned_repo,
            )

        return output

    def visit_func_expr(self, node: FunctionExpression) -> Value:
        if (expr := super().visit_func_expr(node)) is not NotImplemented:
            return expr

        assert isinstance(node.callee, IdentifierExpression)

        symbol = self.symbols.get(node.callee.name)

        if not symbol:
            return UnreachableValue()

        assert isinstance(symbol, FunctionValue)

        if isinstance(symbol.func, FunctionDefStatement):
            func = symbol.func

            with self.new_scope():
                args = [arg.accept(self) for arg in node.args]

                for name, arg in zip(func.arg_names, args, strict=True):
                    self.symbols[name] = arg

                return func.body.accept(self)

        if callable(symbol.func):
            # TODO: make this type-safe
            return symbol.func(node)

        return UnreachableValue()

    def visit_cache_stmt(self, node: CacheStatement) -> Value:
        assert self.trigger

        files = [file.accept(self) for file in node.files]
        cache_key = node.using.accept(self)

        assert isinstance(cache_key, StringValue)

        cache_repo = CacheRepo()

        if cache_repo.key_exists(self.trigger.repository_url, cache_key.value):
            cmd = RestoreCache(cache_repo)
            cmd.handle(
                self.trigger.repository_url,
                cache_key.value,
                self.cloned_repo,
            )

            return UnitValue()

        self.cache_key = cache_key.value
        self.cached_files = []

        for filename in files:
            assert isinstance(filename, StringValue)

            self.cached_files.append(Path(filename.value))

        return UnitValue()

    def _start_container(self, image: str) -> None:
        # TODO: add timeout
        process = subprocess.run(  # noqa: PLW1510
            [
                self.program,
                "run",
                "--rm",
                "--detach",
                "--entrypoint",
                "sleep",
                "--mount",
                f"type=bind,src={self.cloned_repo},dst={self.temp_dir}",
                image,
                "infinity",
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

    def _container_exec(self, args: list[str]) -> int:
        # This command is a hack to make sure we are in cwd from the last
        # command that was ran. Because each `exec` command is executed in the
        # container WORKDIR folder the cwd is not saved after `exec` finishes.
        # To fix this we attempt to cd into the saved directory, run the
        # command, then save the cwd for the next command. We also keep track
        # of the exit code so that we can return it after saving the cwd.

        # `args` explicitly DOES NOT use `shlex.join` so that shell features
        # like piping, env vars, and so forth can be used.
        cmd = " ;\n".join(
            [
                f'cd "$(cat /tmp/__cicada_cwd 2> /dev/null || echo "{self.temp_dir}")"',  # noqa: E501
                " ".join(args),
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
            *get_env_vars_from_env_record(
                cast(RecordValue, self.symbols["env"])
            ),
        ]

        # Add "-e" flag before each env var
        extra_args = chain.from_iterable(["-e", x] for x in env_vars)

        process = subprocess.Popen(
            [
                self.program,
                "exec",
                "-e",
                f"COLUMNS={self.max_columns}",
                *extra_args,
                "-t",
                *self.program_specific_flags(),
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
        return f"/tmp/{self.uuid}"

    def hashOf(self, node: FunctionExpression) -> StringValue:  # noqa: N802
        args: list[str] = []

        for arg in node.args:
            value = arg.accept(self)

            assert isinstance(value, StringValue)

            args.append(value.value)

        shell_code = f"""\
        cd "$(cat /tmp/__cicada_cwd 2> /dev/null || echo "{self.temp_dir}")"

        set -o pipefail

        (
            IFS=
            files=()

            for file in {shlex.join(args)}; do
                files+=($file)
            done

            IFS=$'\\n'
            sorted=($(sort <<< "${{files[*]}}"))
            unset IFS

            for file in "${{sorted[@]}}"; do
                cat "$file"
                [ "$?" = "1" ] && exit 1;
            done

            # DO NOT REMOVE :
            :
        ) | sha256sum - | awk '{{print $1}}'
        """

        process = subprocess.run(  # noqa: PLW1510
            [
                self.program,
                "exec",
                "-t",
                *self.program_specific_flags(),
                self.container_id,
                "/bin/bash",
                "-c",
                shell_code,
            ],
            capture_output=True,
        )

        lines = process.stdout.decode().splitlines()

        if process.returncode:
            if len(lines) > 1:
                # Strip "cat: " prefix
                msg = lines[0][5:]
            else:
                msg = "One or more files could not be found"

            self.terminal.append(f"hashOf(): {msg}\r\n".encode())

            raise CommandFailed(1)

        return StringValue(lines[0].strip())

    def builtin_shell(self, node: FunctionExpression) -> Value:
        # TODO: turn this into a function
        args: list[str] = []

        for arg in node.args:
            value = arg.accept(self)

            assert isinstance(value, StringValue)

            args.append(value.value)

        exit_code = self._container_exec(args)

        if exit_code != 0:
            raise CommandFailed(exit_code)

        return RecordValue({}, RecordType())

    def builtin_print(self, node: FunctionExpression) -> Value:
        args: list[str] = []

        for arg in node.args:
            value = arg.accept(self)

            assert isinstance(value, StringValue)

            args.append(value.value)

        self.terminal.append(" ".join(args).encode() + b"\r\n")

        return UnitValue()

    def program_specific_flags(self) -> list[str]:
        # TODO: Fix GitHub Codespaces emitting warnings
        return ["--log-level=error"] if self.program == "podman" else []


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


def get_env_vars_from_env_record(env: RecordValue) -> list[str]:
    return [f"{k}={cast(StringValue, v).value}" for k, v in env.value.items()]
