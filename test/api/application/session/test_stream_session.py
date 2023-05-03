from asyncio import create_task
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from cicada.api.application.session.stream_session import StreamSession
from cicada.api.domain.session import SessionStatus
from cicada.api.domain.terminal_session import TerminalSession


class SlimSession:
    """
    A slimmed down session which only includes the session status for testing
    purposes.
    """

    status = SessionStatus.SUCCESS


async def test_stream_full_session() -> None:
    terminal_session_repo = MagicMock()
    session_repo = MagicMock()
    session_stopper = AsyncMock()

    session_id = uuid4()

    terminal = TerminalSession()
    terminal.handle_line("hello")
    terminal.handle_line("world")
    terminal.finish()
    terminal_session_repo.get_by_session_id.return_value = terminal

    session_repo.get_session_by_session_id.return_value = SlimSession()

    stream = StreamSession(
        terminal_session_repo=terminal_session_repo,
        session_repo=session_repo,
        stop_session=session_stopper,
    )

    data = [data async for data in stream.stream(session_id, run=1)]

    assert data == [{"stdout": ["hello", "world"]}, {"status": "SUCCESS"}]

    session_stopper.assert_not_called()


async def test_stop_session_mid_stream() -> None:
    terminal_session_repo = MagicMock()
    session_repo = MagicMock()
    session_stopper = AsyncMock()

    session_id = uuid4()

    terminal = TerminalSession()
    terminal.handle_line("hello")
    terminal.handle_line("world")
    terminal_session_repo.get_by_session_id.return_value = terminal

    session_repo.get_session_by_session_id.return_value = SlimSession()

    stream = StreamSession(
        terminal_session_repo=terminal_session_repo,
        session_repo=session_repo,
        stop_session=session_stopper,
    )

    async def read_stream():  # type: ignore[no-untyped-def]
        return [data async for data in stream.stream(session_id, run=1)]

    task = create_task(read_stream())  # type: ignore[no-untyped-call]

    stream.send_command("STOP")
    data = await task

    assert data == [{"stdout": ["hello", "world"]}, {"status": "STOPPED"}]

    session_stopper.assert_called()


async def test_stream_non_existent_session_fails() -> None:
    terminal_session_repo = MagicMock()
    session_repo = MagicMock()
    session_stopper = AsyncMock()

    terminal_session_repo.get_by_session_id.return_value = None

    stream = StreamSession(
        terminal_session_repo=terminal_session_repo,
        session_repo=MagicMock(),
        stop_session=session_stopper,
    )

    data = [data async for data in stream.stream(uuid4(), run=1)]

    assert data == [{"error": "Session not found"}]

    session_stopper.assert_not_called()
    session_repo.get_session_by_session_id.assert_not_called()
