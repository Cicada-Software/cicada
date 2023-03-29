from abc import ABC, abstractmethod
from uuid import UUID

from cicada.api.domain.terminal_session import TerminalSession


class ITerminalSessionRepo(ABC):
    @abstractmethod
    def create(self, session_id: UUID, run: int = -1) -> TerminalSession:
        ...

    @abstractmethod
    def add_line(self, session_id: UUID, line: str, run: int = -1) -> None:
        ...

    @abstractmethod
    def get_by_session_id(
        self, session_id: UUID, run: int = -1
    ) -> TerminalSession | None:
        ...
