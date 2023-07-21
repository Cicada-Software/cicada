import json

import pytest

from cicada.common.json import asjson
from cicada.domain.datetime import UtcDatetime
from cicada.domain.triggers import CommitTrigger, GitSha, json_to_trigger


def test_convert_trigger_to_and_from_json() -> None:
    trigger = CommitTrigger(
        provider="github",
        repository_url="",
        sha=GitSha("DEADBEEF"),
        ref="refs/heads/master",
        branch="master",
        author="dosisod",
        message="",
        committed_on=UtcDatetime.now(),
    )

    json_str = json.dumps(asjson(trigger))

    new_trigger = json_to_trigger(json_str)

    assert new_trigger == trigger


def test_sha_validation() -> None:
    tests = ["12345678", "1" * 40, "A" * 40, "a" * 40]

    for test in tests:
        sha = GitSha(test)

        assert str(sha) == test


def test_invalid_sha_raises_error() -> None:
    tests = ["invalid", "", "1" * 10, "x12345678x"]

    for test in tests:
        with pytest.raises(ValueError, match='SHA ".*" is invalid'):
            GitSha(test)
