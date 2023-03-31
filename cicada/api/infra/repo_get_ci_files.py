import logging
import shlex
from asyncio.subprocess import PIPE, STDOUT, create_subprocess_exec
from pathlib import Path
from tempfile import TemporaryDirectory

from cicada.api.domain.triggers import Trigger
from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import AstError
from cicada.ast.semantic_analysis import IgnoreWorkflow
from cicada.eval.find_files import find_ci_files
from cicada.eval.on_statement_visitor import (
    OnStatementEvalVisitor,
    ShouldRunWorkflow,
)


# TODO: replace `ref` with `sha`
async def repo_get_ci_files(
    url: str, ref: str, trigger: Trigger
) -> list[Path | AstError]:  # pragma: no cover
    tmp_dir: str | None = None

    try:
        with TemporaryDirectory() as dir:
            tmp_dir = dir

            # TODO: use python git library instead
            cmds = [
                ["git", "init"],
                ["git", "remote", "add", "origin", shlex.quote(url)],
                ["git", "fetch", "--depth", "1", "origin", shlex.quote(ref)],
                ["git", "checkout", "FETCH_HEAD"],
            ]

            for args in cmds:
                process = await create_subprocess_exec(
                    args[0],
                    *args[1:],
                    stdout=PIPE,
                    stderr=STDOUT,
                    cwd=dir,
                )

                await process.wait()

                print(args, "->", process.returncode)

                if process.stdout and (data := await process.stdout.read()):
                    print(data.decode())

                if process.returncode != 0:
                    return []

            return folder_get_runnable_ci_files(Path(dir), trigger)

    except Exception:  # noqa: BLE001
        logger = logging.getLogger("cicada")

        logger.error(
            f'Issue gathering workflows or deleting temp dir "{tmp_dir}"'
        )

    return []


def folder_get_runnable_ci_files(
    folder: Path, trigger: Trigger
) -> list[Path | AstError]:  # pragma: no cover
    files_or_errors: list[Path | AstError] = []

    for file in find_ci_files(folder):
        print(f"checking {file}")

        try:
            tree = parse_and_analyze(file.read_text(), trigger)

            visitor = OnStatementEvalVisitor(trigger)

            try:
                tree.accept(visitor)

            except ShouldRunWorkflow as ex:
                print(f"on statement reached: {ex.should_run}")
                if ex.should_run:
                    files_or_errors.append(file)

            print("checking next file")

        except IgnoreWorkflow:
            print("ignoring workflow")
            pass

        except AstError as err:
            print("file contains errors")
            err.filename = str(file.relative_to(folder))

            files_or_errors.append(err)

    return files_or_errors
