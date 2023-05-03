from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cicada.api.application.exceptions import InvalidRequest, NotFound
from cicada.api.application.session.stop_session import StopSession
from cicada.api.common.datetime import UtcDatetime
from cicada.api.domain.session import Session, SessionStatus
from cicada.api.domain.triggers import CommitTrigger, GitSha


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
    trigger = CommitTrigger(
        repository_url="",
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="",
        provider="github",
        message="",
        committed_on=UtcDatetime.now(),
    )

    session = Session(id=uuid4(), trigger=trigger)

    session_repo = MagicMock()
    session_repo.get_session_by_session_id.return_value = session

    terminator_called = False

    async def terminator(_: Session) -> None:
        nonlocal terminator_called
        terminator_called = True

    cmd = StopSession(session_repo, {"github": terminator})
    await cmd.handle(session.id)

    assert session.status == SessionStatus.STOPPED
    assert session.finished_at
    assert terminator_called
    assert session_repo.update.call_count == 1


async def test_provider_terminator_not_called_if_provider_doesnt_match() -> None:  # noqa: E501
    trigger = CommitTrigger(
        repository_url="",
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="",
        provider="github",
        message="",
        committed_on=UtcDatetime.now(),
    )

    session = Session(id=uuid4(), trigger=trigger)

    session_repo = MagicMock()
    session_repo.get_session_by_session_id.return_value = session

    terminator_called = False

    async def terminator(_: Session) -> None:
        nonlocal terminator_called
        terminator_called = True

    cmd = StopSession(session_repo, {"gitlab": terminator})
    await cmd.handle(session.id)

    assert session.status == SessionStatus.STOPPED
    assert session.finished_at
    assert not terminator_called
    assert session_repo.update.call_count == 1
