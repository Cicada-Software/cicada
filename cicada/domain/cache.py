from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, NewType
from uuid import UUID

from cicada.domain.datetime import UtcDatetime
from cicada.domain.session import WorkflowId

CacheObjectId = NewType("CacheObjectId", UUID)


class CacheKey:
    MAX_LEN: ClassVar[int] = 256
    BANNED_CHARS: ClassVar[str] = ":\"'<>&+=/\\"

    _key: str

    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("Cache key cannot be empty")

        if len(key) > self.MAX_LEN:
            raise ValueError(
                f"Cache key cannot be greater than {self.MAX_LEN} characters, got {len(key)}."
            )

        if set(key).intersection(self.BANNED_CHARS):
            banned = self.BANNED_CHARS.replace('"', r"\"")

            raise ValueError(
                f'Cache key cannot contain any of the following characters: "{banned}"'
            )

        self._key = key

    def __str__(self) -> str:
        return self._key

    def __eq__(self, o: object) -> bool:
        return isinstance(o, CacheKey) and str(o) == str(self)


@dataclass(frozen=True)
class CacheObject:
    DAYS_TILL_EXPIRED: ClassVar[int] = 14

    id: CacheObjectId
    repository_url: str
    key: CacheKey

    workflow_id: WorkflowId

    # Filename that contains the underlying data for the cache object
    file: Path

    created_at: UtcDatetime = field(default_factory=UtcDatetime.now)
