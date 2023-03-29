from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from cicada.api.common.datetime import Datetime

TriggerType = str


GIT_SHA_RE = re.compile("^[a-f0-9]{8}([a-f0-9]{32})?$", re.IGNORECASE)


class GitSha:
    def __init__(self, sha: str) -> None:
        if not GIT_SHA_RE.match(sha):
            raise ValueError(f'SHA "{sha}" is invalid')

        self.sha = sha

    def __str__(self) -> str:
        return self.sha

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}("{self}")'

    def __eq__(self, o: object) -> bool:
        return isinstance(o, GitSha) and self.sha == o.sha


@dataclass(kw_only=True)
class Trigger:
    type: ClassVar[TriggerType]
    provider: Literal["github", "gitlab"]
    repository_url: str
    sha: GitSha | None = None
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, **kw: str) -> Trigger:
        raise NotImplementedError()


@dataclass(kw_only=True)
class CommitTrigger(Trigger):
    type = "git.push"
    author: str
    message: str
    committed_on: Datetime
    sha: GitSha
    # authored_on: Datetime
    ref: str
    branch: str = ""

    def __post_init__(self) -> None:
        if not self.branch:
            # TODO: this assumes the ref is in the form "refs/X/branch", so if
            # there are not 2 slashes in the ref, the branch will be empty.
            # This might be fine, but something to point out.
            self.branch = "/".join(self.ref.split("/")[2:])

    @classmethod
    def from_dict(cls, **kw: str) -> CommitTrigger:
        assert kw.pop("type") == cls.type

        return cls(
            sha=GitSha(kw.pop("sha")),
            committed_on=Datetime.fromisoformat(kw.pop("committed_on")),
            **kw,  # type: ignore
        )


@dataclass(kw_only=True)
class IssueTrigger(Trigger):
    # TODO: allow for creation of generic `issue` events

    id: str
    title: str
    submitted_by: str
    is_locked: bool
    opened_at: Datetime
    body: str


@dataclass(kw_only=True)
class IssueOpenTrigger(IssueTrigger):
    type = "issue.open"

    @classmethod
    def from_dict(cls, **kw: str) -> IssueOpenTrigger:
        assert kw.pop("type") == cls.type

        return cls(
            sha=GitSha(kw.pop("sha")) if "sha" in kw else None,
            is_locked=bool(kw.pop("is_locked")),
            opened_at=Datetime.fromisoformat(kw.pop("opened_at")),
            **kw,  # type: ignore
        )


@dataclass(kw_only=True)
class IssueCloseTrigger(IssueTrigger):
    type = "issue.close"
    closed_at: Datetime

    @classmethod
    def from_dict(cls, **kw: str) -> IssueCloseTrigger:
        assert kw.pop("type") == cls.type

        return cls(
            sha=GitSha(kw.pop("sha")) if "sha" in kw else None,
            is_locked=bool(kw.pop("is_locked")),
            opened_at=Datetime.fromisoformat(kw.pop("opened_at")),
            closed_at=Datetime.fromisoformat(kw.pop("closed_at")),
            **kw,  # type: ignore
        )


def json_to_trigger(j: str) -> Trigger:
    payload = json.loads(j)

    for value in globals().values():
        if (
            value != Trigger
            and isinstance(value, type)
            and issubclass(value, Trigger)
            and hasattr(value, "type")
            and payload.get("type") == value.type
        ):
            return value.from_dict(**payload)

    assert False
