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
    logger = logging.getLogger("cicada")

    try:
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
                cwd=cloned_repo,
            )

            await process.wait()

            if process.returncode != 0:
                logger.error(
                    f"Could not clone repository {trigger.repository_url}"
                )
                return []

        return folder_get_runnable_ci_files(cloned_repo, trigger)

    except Exception:
        logger.exception("Issue gathering workflows")

    return []


def folder_get_runnable_ci_files(
    folder: Path, trigger: Trigger
) -> list[FileNode | AstError]:  # pragma: no cover
    files_or_errors: list[FileNode | AstError] = []

    for file in find_ci_files(folder):
        try:
            tree = parse_and_analyze(file.read_text(), trigger)

            visitor = OnStatementEvalVisitor(trigger)

            try:
                tree.accept(visitor)

            except ShouldRunWorkflow as ex:
                if ex.should_run:
                    tree.file = file
                    files_or_errors.append(tree)

        except IgnoreWorkflow:
            pass

        except AstError as err:
            err.filename = str(file.relative_to(folder))

            files_or_errors.append(err)

    return sorted(files_or_errors, key=extract_filename)


def extract_filename(item: FileNode | AstError) -> str:
    if isinstance(item, FileNode):
        return str(item.file or "")

    return item.filename or ""
