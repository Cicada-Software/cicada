from asyncio import create_task
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from cicada.application.session.stream_session import StreamSession
from cicada.domain.session import Session, SessionStatus, Workflow, WorkflowStatus
from cicada.domain.terminal_session import TerminalSession
from test.common import build
from test.domain.repo.mock_session_repo import MockSessionRepo


class SlimSession:
    """
    A slimmed down session which only includes the session status for testing
    purposes.
    """

    status = SessionStatus.SUCCESS


async def test_stream_full_session() -> None:
    terminal_session_repo = MagicMock()
    session_repo = MockSessionRepo()
    session_stopper = AsyncMock()

    terminal = TerminalSession()
    terminal.append(b"hello\n")
    terminal.append(b"world")
    terminal.finish()
    terminal_session_repo.get_by_workflow_id.return_value = terminal

    workflow = build(Workflow)
    workflow.finish(WorkflowStatus.SUCCESS)
    session = build(Session, runs=[workflow])
    session.finish()

    session_repo.create(session)
    session_repo.create_workflow(workflow, session)

    stream = StreamSession(
        terminal_session_repo=terminal_session_repo,
        session_repo=session_repo,
        stop_session=session_stopper,
    )

    data = [data async for data in stream.stream(session.id, run=1)]

    assert data == [
        {"stdout": "hello\nworld", "workflow": str(workflow.id)},
        {"status": "SUCCESS"},
    ]

    session_stopper.assert_not_called()


async def test_stop_session_mid_stream() -> None:
    terminal_session_repo = MagicMock()
    session_repo = MockSessionRepo()
    session_stopper = AsyncMock()

    terminal = TerminalSession()
    terminal.append(b"hello\n")
    terminal.append(b"world")
    terminal_session_repo.get_by_workflow_id.return_value = terminal

    workflow = build(Workflow, status=WorkflowStatus.PENDING)
    session = build(Session, runs=[workflow])

    session_repo.create(session)
    session_repo.create_workflow(workflow, session)

    stream = StreamSession(
        terminal_session_repo=terminal_session_repo,
        session_repo=session_repo,
        stop_session=session_stopper,
    )

    async def read_stream():  # type: ignore[no-untyped-def]
        return [data async for data in stream.stream(session.id, run=1)]

    task = create_task(read_stream())  # type: ignore[no-untyped-call]

    stream.send_command("STOP")
    data = await task

    assert data == [
        {"stdout": "hello\nworld", "workflow": str(workflow.id)},
        {"status": "STOPPED"},
    ]

    session_stopper.assert_called()


async def test_stream_non_existent_session_fails() -> None:
    terminal_session_repo = MagicMock()
    session_repo = MockSessionRepo()
    session_stopper = AsyncMock()

    terminal_session_repo.get_by_workflow_id.return_value = None

    stream = StreamSession(
        terminal_session_repo=terminal_session_repo,
        session_repo=session_repo,
        stop_session=session_stopper,
    )

    data = [data async for data in stream.stream(uuid4(), run=1)]

    assert data == [{"error": "Session not found"}]

    session_stopper.assert_not_called()
