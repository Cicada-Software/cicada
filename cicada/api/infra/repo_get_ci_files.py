import logging
import shlex
from asyncio.subprocess import PIPE, STDOUT, create_subprocess_exec
from pathlib import Path

from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import AstError
from cicada.ast.nodes import FileNode
from cicada.ast.semantic_analysis import IgnoreWorkflow
from cicada.domain.triggers import Trigger
from cicada.eval.find_files import find_ci_files
from cicada.eval.on_statement_visitor import (
    OnStatementEvalVisitor,
    ShouldRunWorkflow,
)


# TODO: replace `ref` with `sha`
async def repo_get_ci_files(
    url: str,
    ref: str,
    trigger: Trigger,
    cloned_repo: Path,
) -> list[FileNode | AstError]:  # pragma: no cover
    try:
        # TODO: use python git library instead
        cmds = [
            ["git", "init"],
            ["git", "remote", "add", "origin", shlex.quote(url)],
            ["git", "fetch", "--depth", "1", "origin", shlex.quote(ref)],
            ["git", "checkout", "FETCH_HEAD"],
        ]

        logger = logging.getLogger("cicada")

        for args in cmds:
            process = await create_subprocess_exec(
                args[0],
                *args[1:],
                stdout=PIPE,
                stderr=STDOUT,
                cwd=cloned_repo,
            )

            await process.wait()

            logger.debug(f"{args} -> {process.returncode}")

            if process.stdout and (data := await process.stdout.read()):
                logger.debug(data.decode())

            if process.returncode != 0:
                return []

        return folder_get_runnable_ci_files(cloned_repo, trigger)

    except Exception:
        logger = logging.getLogger("cicada")
        logger.exception("Issue gathering workflows")

    return []


def folder_get_runnable_ci_files(
    folder: Path, trigger: Trigger
) -> list[FileNode | AstError]:  # pragma: no cover
    files_or_errors: list[FileNode | AstError] = []

    logger = logging.getLogger("cicada")

    for file in find_ci_files(folder):
        logger.debug(f"checking {file}")

        try:
            tree = parse_and_analyze(file.read_text(), trigger)

            visitor = OnStatementEvalVisitor(trigger)

            try:
                tree.accept(visitor)

            except ShouldRunWorkflow as ex:
                logger.debug(f"on statement reached: {ex.should_run}")
                if ex.should_run:
                    tree.file = file
                    files_or_errors.append(tree)

            logger.debug("checking next file")

        except IgnoreWorkflow:
            logger.debug("ignoring workflow")

            pass

        except AstError as err:
            logger.debug("file contains errors")

            err.filename = str(file.relative_to(folder))

            files_or_errors.append(err)

    return files_or_errors
