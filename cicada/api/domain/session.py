from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from cicada.api.common.datetime import UtcDatetime

from .triggers import Trigger


class SessionStatus(Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    STOPPED = "STOPPED"


# TODO: use typing.NewType
SessionId = UUID


@dataclass
class Session:
    id: SessionId
    trigger: Trigger
    status: SessionStatus = SessionStatus.PENDING
    started_at: UtcDatetime = field(default_factory=UtcDatetime.now)
    finished_at: UtcDatetime | None = None
    run: int = 1

    def __post_init__(self) -> None:
        assert self.run >= 1

    def finish(self, status: SessionStatus) -> None:
        self.status = status
        self.finished_at = UtcDatetime.now()
