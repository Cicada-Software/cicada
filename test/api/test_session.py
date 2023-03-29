from uuid import uuid4

import pytest

from cicada.api.common.datetime import UtcDatetime
from cicada.api.domain.session import Session, SessionStatus
from cicada.api.domain.triggers import CommitTrigger, GitSha


def test_session_creation() -> None:
    trigger = CommitTrigger(
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="",
        message="hello",
        committed_on=UtcDatetime.now(),
        provider="github",
        repository_url="",
    )

    session = Session(id=uuid4(), trigger=trigger)

    assert session.id
    assert session.status == SessionStatus.PENDING
    assert session.run == 1
    assert session.started_at
    assert not session.finished_at


def test_run_number_must_be_greater_than_one() -> None:
    trigger = CommitTrigger(
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="",
        message="hello",
        committed_on=UtcDatetime.now(),
        provider="github",
        repository_url="",
    )

    with pytest.raises(AssertionError):
        Session(id=uuid4(), trigger=trigger, run=0)
