import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from cicada.application.session.rerun_session import RerunSession
from cicada.domain.datetime import UtcDatetime
from cicada.domain.session import Session, SessionStatus
from cicada.domain.terminal_session import TerminalSession
from cicada.domain.triggers import CommitTrigger, GitSha
from test.api.application.session.test_make_session_from_trigger import (
    AsyncTap,
    make_fake_repository_repo,
)


async def test_reran_session_is_created_and_ran() -> None:
    tap = AsyncTap()

    async def dummy_check_runner(session: Session, *_) -> None:  # type: ignore
        await tap.wait_for_close()

        session.finish(SessionStatus.SUCCESS)

    session_repo = MagicMock()
    terminal_session_repo = MagicMock()

    terminal_session = TerminalSession()
    terminal_session_repo.create.return_value = terminal_session

    cmd = RerunSession(
        session_repo,
        terminal_session_repo,
        gather_workflows=AsyncMock(return_value=[1]),
        workflow_runner=dummy_check_runner,
        env_repo=MagicMock(),
        repository_repo=make_fake_repository_repo(),
    )

    session = Session(
        id=uuid4(),
        trigger=CommitTrigger(
            sha=GitSha("deadbeef"),
            ref="refs/heads/master",
            author="",
            message="",
            committed_on=UtcDatetime.now(),
            repository_url="",
            provider="github",
        ),
    )

    session_repo.get_session_by_session_id.return_value = session

    handle = asyncio.create_task(cmd.handle(session))

    session_repo.create.called_once()

    # stop execution during workflow runner execution, check that the session
    # hasn't finished, that it was passed the correct args, etc.
    async with tap.open():
        new_session: Session = session_repo.create.call_args[0][0]

        assert new_session.id == session.id
        assert new_session.trigger == session.trigger
        assert new_session.run == 2
        assert new_session.started_at != session.started_at
        assert not new_session.finished_at

    # finish the rest of the workflow
    await handle

    updated_session: Session = session_repo.update.call_args[0][0]

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
    )

    session = Session(
        id=uuid4(),
        trigger=CommitTrigger(
            sha=GitSha("deadbeef"),
            ref="refs/heads/master",
            author="",
            message="",
            committed_on=UtcDatetime.now(),
            repository_url="",
            provider="github",
        ),
    )

    await cmd.handle(session)

    session_repo.create.assert_not_called()
    terminal_session_repo.create.assert_not_called()
