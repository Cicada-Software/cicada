from abc import ABC, abstractmethod
from uuid import UUID

from cicada.api.domain.session import Session
from cicada.api.domain.user import User


class ISessionRepo(ABC):
    @abstractmethod
    def create(self, session: Session) -> None:
        ...

    @abstractmethod
    def update(self, session: Session) -> None:
        ...

    @abstractmethod
    def get_session_by_session_id(
        self,
        uuid: UUID,
        run: int = -1,
        user: User | None = None,
    ) -> Session | None:
        ...

    @abstractmethod
    def get_recent_sessions(self, user: User) -> list[Session]:
        ...

    @abstractmethod
    def get_recent_sessions_for_repo(
        self, user: User, repository_url: str
    ) -> list[Session]:
        ...

    @abstractmethod
    def get_runs_for_session(self, user: User, uuid: UUID) -> list[Session]:
        ...

    @abstractmethod
    def get_recent_sessions_as_admin(self) -> list[Session]:
        """
        Get all recent sessions regardless of who started them. This should
        only be used by people with admin perms, or for testing.
        """

    @abstractmethod
    def can_user_see_session(self, user: User, session: Session) -> bool:
        ...
