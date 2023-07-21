from abc import ABC, abstractmethod

from cicada.domain.session import SessionId
from cicada.domain.terminal_session import TerminalSession


class ITerminalSessionRepo(ABC):
    @abstractmethod
    def create(self, session_id: SessionId, run: int = -1) -> TerminalSession:
        ...

    @abstractmethod
    def append_to_session(
        self, session_id: SessionId, data: bytes, run: int = -1
    ) -> None:
        ...

    @abstractmethod
    def get_by_session_id(
        self, session_id: SessionId, run: int = -1
    ) -> TerminalSession | None:
        ...
