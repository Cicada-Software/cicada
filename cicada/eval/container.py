from __future__ import annotations

import asyncio
import logging
import os
import pty
import re
import shlex
import shutil
import sys
import termios
from asyncio import subprocess
from asyncio.subprocess import PIPE, STDOUT
from contextlib import suppress
from copy import deepcopy
from decimal import Decimal
from functools import partial
from inspect import isawaitable
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from cicada.api.infra.cache_repo import CacheRepo
from cicada.application.cache.cache_files import CacheFilesForWorkflow
from cicada.application.cache.restore_cache import RestoreCache
from cicada.ast.generate import SHELL_ALIASES
from cicada.ast.nodes import (
    CacheStatement,
    FileNode,
    FunctionAnnotation,
    FunctionDefStatement,
    FunctionExpression,
    FunctionValue,
    IdentifierExpression,
    NumericValue,
    RecordValue,
    StringValue,
    UnitValue,
    UnreachableValue,
    Value,
)
from cicada.ast.semantic_analysis import StringCoercibleType
from cicada.ast.types import CommandType, FunctionType, StringType, UnitType, VariadicTypeArg
from cicada.domain.cache import CacheKey
from cicada.domain.triggers import CommitTrigger
from cicada.eval.constexpr_visitor import CommandFailed, ConstexprEvalVisitor, WorkflowFailure

if TYPE_CHECKING:
    from cicada.domain.session import Workflow
    from cicada.domain.terminal_session import TerminalSession
    from cicada.domain.triggers import Trigger


class ContainerTermination(WorkflowFailure):
    pass


def generate_default_sub_workflow_title(name: str) -> str:
    """
    Given a function name, try to make a pretty printed, title cased version.
    """

    name = name.replace("_", " ")
    parts = chain.from_iterable(x.split() for x in re.split("(?<=[a-z])(?=[A-Z])", name))

    return " ".join(x.title() for x in parts)


async def spawn_sub_workflow(self: RemoteContainerEvalVisitor, func: FunctionDefStatement) -> None:
    process = await subprocess.create_subprocess_exec(
        self.program,
        "commit",
        "--pause=true",
        self.container_id,
        stdout=PIPE,
        stderr=STDOUT,
    )

    await process.wait()

    if process.returncode != 0:
        raise CommandFailed(1)

    assert process.stdout

    cloned_image_id = (await process.stdout.read()).strip().splitlines()[-1].decode()

    sub_workflow = self.workflow.make_subworkflow()

    # TODO: allow for changing sub workflow title via title statement
    sub_workflow.title = generate_default_sub_workflow_title(func.name)

    async def run_sub_workflow(visitor: RemoteContainerEvalVisitor) -> None:
        with TemporaryDirectory() as dir:
            copy = Path(dir)

            # TODO: move to separate function
            # TODO: io bound, run in separate executor
            shutil.copytree(self.cloned_repo, copy, dirs_exist_ok=True)

            visitor.image = cloned_image_id
            visitor.cloned_repo = copy

            await visitor.setup()
            await func.body.accept(visitor)

    visitor = deepcopy(self)

    self.sub_workflows.put_nowait((visitor, sub_workflow, run_sub_workflow(visitor)))


class RemoteContainerEvalVisitor(ConstexprEvalVisitor):  # pragma: no cover
    container_id: str

    # Program used to run container (ie, docker or podman)
    program: str

    max_columns: int = 120

    # TODO: isolate this logic in consteval visitor (or a visitor that estends
    # from it.
    cached_files: list[Path] | None
    cache_key: str | None

    sub_workflows: asyncio.Queue  # type: ignore[type-arg]

    def __init__(
        self,
        cloned_repo: Path,
        trigger: Trigger,
        terminal: TerminalSession,
        image: str,
        program: str,
        workflow: Workflow,
        sub_workflows: asyncio.Queue,  # type: ignore[type-arg]
    ) -> None:
        super().__init__(trigger)

        self.trigger = trigger
        self.image = image

        self.terminal = terminal
        self.cloned_repo = cloned_repo

        self.uuid = uuid4()
        self.program = program

        self.cached_files = None
        self.cache_key = None

        self.workflow = workflow

        self.sub_workflows = sub_workflows

        # TODO: deduplicate this monstrosity
        built_in_symbols = {
            "shell": FunctionValue(
                type=FunctionType([VariadicTypeArg(StringCoercibleType)], rtype=CommandType()),
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
                func=self.hash_of,
            ),
            **{
                alias: FunctionValue(
                    FunctionType([StringCoercibleType], rtype=CommandType()),
                    func=self.builtin_shell,
                )
                for alias in SHELL_ALIASES
            },
        }

        self.symbols.update(built_in_symbols)

    def __deepcopy__(self, memo: Any) -> RemoteContainerEvalVisitor:  # type: ignore
        assert self.trigger

        copy = RemoteContainerEvalVisitor(
            deepcopy(self.cloned_repo, memo),
            deepcopy(self.trigger, memo),
            self.terminal,
            self.image,
            self.program,
            self.workflow,
            self.sub_workflows,
        )
        copy.symbols = deepcopy(self.symbols, memo)
        copy.uuid = self.uuid

        return copy

    async def setup(self) -> None:
        await self._start_container(self.image)

    async def cleanup(self) -> None:
        process = await subprocess.create_subprocess_exec(
            self.program,
            "kill",
            self.container_id,
            stdout=PIPE,
            stderr=STDOUT,
        )

        await process.wait()

        if process.returncode != 0:
            logging.getLogger("cicada").error(f"Could not kill container id: {self.container_id}")

    async def visit_file_node(self, node: FileNode) -> Value:
        output = await super().visit_file_node(node)

        if isinstance(output, UnitValue) and self.cached_files and self.cache_key and self.trigger:
            cmd = CacheFilesForWorkflow(CacheRepo())

            f = partial(
                cmd.handle,
                self.cached_files,
                CacheKey(self.cache_key),
                self.trigger.repository_url,
                self.workflow.id,
                self.cloned_repo,
            )

            await asyncio.get_event_loop().run_in_executor(None, f)

        return output

    async def visit_func_expr(self, node: FunctionExpression) -> Value:
        if (expr := await super().visit_func_expr(node)) is not NotImplemented:
            return expr

        assert isinstance(node.callee, IdentifierExpression)

        symbol = self.symbols.get(node.callee.name)

        if not symbol:
            return UnreachableValue()

        assert isinstance(symbol, FunctionValue)

        if isinstance(symbol.func, FunctionDefStatement):
            func = symbol.func

            with self.new_scope():
                args = [await arg.accept(self) for arg in node.args]

                for name, arg in zip(func.arg_names, args, strict=True):
                    self.symbols[name] = arg

                if self.is_workflow_function(func):
                    await spawn_sub_workflow(self, func)

                    return UnitValue()

                return await func.body.accept(self)

        if callable(symbol.func):
            # TODO: make this type-safe
            f = symbol.func(self, node)

            if isawaitable(f):
                return cast(Value, await f)

            return cast(Value, f)

        return UnreachableValue()

    async def visit_cache_stmt(self, node: CacheStatement) -> Value:
        assert self.trigger

        files = [await file.accept(self) for file in node.files]
        cache_key = await node.using.accept(self)

        assert isinstance(cache_key, StringValue)

        cache_repo = CacheRepo()

        if cache_repo.key_exists(self.trigger.repository_url, cache_key.value):
            cmd = RestoreCache(cache_repo)

            f = partial(
                cmd.handle,
                self.trigger.repository_url,
                cache_key.value,
                self.cloned_repo,
            )

            await asyncio.get_event_loop().run_in_executor(None, f)

            return UnitValue()

        self.cache_key = cache_key.value
        self.cached_files = []

        for filename in files:
            assert isinstance(filename, StringValue)

            self.cached_files.append(Path(filename.value))

        return UnitValue()

    def is_workflow_function(self, node: FunctionDefStatement) -> bool:
        match node.annotations:
            case [FunctionAnnotation(IdentifierExpression("workflow"))]:
                return True

        return False

    async def _start_container(self, image: str) -> None:
        # TODO: add timeout
        process = await subprocess.create_subprocess_exec(
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
            stdout=PIPE,
            stderr=STDOUT,
        )
        await process.wait()

        if process.returncode != 0:
            msg = f"Could not start container. Make sure image `{image}` exists and is valid, then retry."  # noqa: E501

            self.terminal.append(msg.encode())

            raise ContainerTermination(1)

        assert process.stdout
        stdout = await process.stdout.read()

        self.container_id = stdout.strip().split(b"\n")[-1].decode().strip()

    async def _container_exec(self, args: list[str]) -> tuple[subprocess.Process, bytes]:
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
                f'cd "$(cat /tmp/__cicada_cwd 2> /dev/null || echo "{self.temp_dir}")"',
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
            *get_env_vars_from_env_record(cast(RecordValue, self.symbols["env"])),
        ]

        # Add "-e" flag before each env var
        extra_args = chain.from_iterable(["-e", x] for x in env_vars)

        process = await subprocess.create_subprocess_exec(
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
            stdout=slave,
            stderr=STDOUT,
            close_fds=True,
        )

        os.close(slave)

        # TODO: move to function
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader(1024, loop)

        file_obj = os.fdopen(master, "rb", closefd=False)

        await loop.connect_read_pipe(
            partial(asyncio.StreamReaderProtocol, reader, loop=loop),
            file_obj,
        )

        stdout = b""

        with suppress(IOError):
            while True:
                data = await reader.read(1024)

                if not data:
                    break

                stdout += data
                self.terminal.append(data)

        await process.wait()

        return process, stdout

    @property
    def temp_dir(self) -> str:
        return f"/tmp/{self.uuid}"

    @staticmethod
    async def hash_of(self: RemoteContainerEvalVisitor, node: FunctionExpression) -> StringValue:
        args: list[str] = []

        for arg in node.args:
            value = await arg.accept(self)

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

        process = await subprocess.create_subprocess_exec(
            self.program,
            "exec",
            "-t",
            *self.program_specific_flags(),
            self.container_id,
            "/bin/bash",
            "-c",
            shell_code,
        )

        assert process.stdout

        lines = (await process.stdout.read()).decode().splitlines()

        if process.returncode:
            if len(lines) > 1:  # noqa: SIM108
                # Strip "cat: " prefix
                msg = lines[0][5:]
            else:
                msg = "One or more files could not be found"

            self.terminal.append(f"hashOf(): {msg}\r\n".encode())

            raise CommandFailed(1)

        return StringValue(lines[0].strip())

    @staticmethod
    async def builtin_shell(self: RemoteContainerEvalVisitor, node: FunctionExpression) -> Value:
        # TODO: turn this into a function
        args: list[str] = []

        for arg in node.args:
            value = await arg.accept(self)

            assert isinstance(value, StringValue)

            args.append(value.value)

        process, stdout = await self._container_exec(args)

        if process.returncode != 0:
            raise CommandFailed(process.returncode or 0)

        return RecordValue(
            {
                "exit_code": NumericValue(Decimal(process.returncode)),
                "stdout": StringValue(stdout.decode()),
            },
            CommandType(),
        )

    @staticmethod
    async def builtin_print(self: RemoteContainerEvalVisitor, node: FunctionExpression) -> Value:
        args: list[str] = []

        for arg in node.args:
            value = await arg.accept(self)

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
