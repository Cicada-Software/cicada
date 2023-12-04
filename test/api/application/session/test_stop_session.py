from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cicada.application.exceptions import InvalidRequest, NotFound
from cicada.application.session.stop_session import StopSession
from cicada.domain.datetime import UtcDatetime
from cicada.domain.session import Session, SessionStatus, Workflow
from test.common import build
from test.domain.repo.mock_session_repo import MockSessionRepo


async def test_stopping_session_that_doesnt_exist_throws_error() -> None:
    session_repo = MagicMock()
    session_repo.get_session_by_session_id.return_value = None

    cmd = StopSession(session_repo, {})

    with pytest.raises(NotFound, match="Session.*not found"):
        await cmd.handle(uuid4())

    assert session_repo.update.call_count == 0


async def test_stopping_already_stopped_session_throws_error() -> None:
    session_repo = MagicMock()

    # Too lazy to actually create the session. I should probably start using
    # a builder to quickly make dummy objects
    session = MagicMock()
    session.finished_at = UtcDatetime.now()

    session_repo.get_session_by_session_id.return_value = session

    cmd = StopSession(session_repo, {})

    with pytest.raises(InvalidRequest, match="Session has already finished"):
        await cmd.handle(uuid4())

    assert session_repo.update.call_count == 0


async def test_stopping_existing_session_stops_it() -> None:
    session = build(Session, status=SessionStatus.PENDING)
    workflow = build(Workflow)

    session_repo = MockSessionRepo()
    session_repo.create(session)
    session_repo.create_workflow(workflow, session)

    terminator_called = False

    async def terminator(_: Session) -> None:
        nonlocal terminator_called
        terminator_called = True

    cmd = StopSession(session_repo, {"github": terminator})
    await cmd.handle(session.id)

    assert session.status == SessionStatus.STOPPED
    assert session.finished_at
    assert terminator_called


async def test_provider_terminator_not_called_if_provider_doesnt_match() -> None:
    session = build(Session, status=SessionStatus.PENDING)
    workflow = build(Workflow)

    session_repo = MockSessionRepo()
    session_repo.create(session)
    session_repo.create_workflow(workflow, session)

    terminator_called = False

    async def terminator(_: Session) -> None:
        nonlocal terminator_called
        terminator_called = True

    cmd = StopSession(session_repo, {"gitlab": terminator})
    await cmd.handle(session.id)

    assert session.status == SessionStatus.STOPPED
    assert session.finished_at
    assert not terminator_called
