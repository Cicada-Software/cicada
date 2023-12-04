import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from cicada.application.session.rerun_session import RerunSession
from cicada.ast.nodes import FileNode
from cicada.domain.session import Session, Workflow, WorkflowStatus
from cicada.domain.terminal_session import TerminalSession
from cicada.domain.triggers import Trigger
from test.api.application.session.test_make_session_from_trigger import (
    AsyncTap,
    make_fake_repository_repo,
)
from test.common import build
from test.domain.repo.mock_session_repo import MockSessionRepo


async def dummy_gather(_: Trigger, repo: Path) -> list[FileNode]:
    return [FileNode([], file=repo / "file.ci")]


async def test_reran_session_is_created_and_ran() -> None:
    tap = AsyncTap()

    async def dummy_check_runner(*args) -> None:  # type: ignore
        await tap.wait_for_close()

        workflow: Workflow = args[-1]
        workflow.finish(WorkflowStatus.SUCCESS)

    session_repo = MockSessionRepo()
    terminal_session_repo = MagicMock()

    terminal_session = TerminalSession()
    terminal_session_repo.create.return_value = terminal_session

    cmd = RerunSession(
        session_repo,
        terminal_session_repo,
        gather_workflows=dummy_gather,
        workflow_runner=dummy_check_runner,
        env_repo=MagicMock(),
        repository_repo=make_fake_repository_repo(),
        installation_repo=MagicMock(),
        secret_repo=MagicMock(),
    )

    session = build(Session, run=1)
    session_repo.create(session)

    handle = asyncio.create_task(cmd.handle(session))

    # stop execution during workflow runner execution, check that the session
    # hasn't finished, that it was passed the correct args, etc.
    async with tap.open():
        new_session = session_repo.get_session_by_session_id(session.id)
        assert new_session

        assert new_session.id == session.id
        assert new_session.trigger == session.trigger
        assert new_session.run == 2
        assert new_session.started_at != session.started_at
        assert not new_session.finished_at

    # finish the rest of the workflow
    await handle

    updated_session = session_repo.get_session_by_session_id(session.id)
    assert updated_session

    assert updated_session.finished_at


async def test_session_not_reran_if_gather_fails() -> None:
    session_repo = MagicMock()
    terminal_session_repo = MagicMock()

    cmd = RerunSession(
        session_repo,
        terminal_session_repo,
        workflow_runner=AsyncMock(),
        gather_workflows=AsyncMock(return_value=[]),
        env_repo=MagicMock(),
        repository_repo=make_fake_repository_repo(),
        installation_repo=MagicMock(),
        secret_repo=MagicMock(),
    )

    session = build(Session, run=1)

    await cmd.handle(session)

    session_repo.create.assert_not_called()
    terminal_session_repo.create.assert_not_called()
