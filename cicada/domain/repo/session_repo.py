from abc import ABC, abstractmethod

from cicada.domain.repo.repository_repo import Permission
from cicada.domain.session import Run, Session, SessionId, Workflow, WorkflowId
from cicada.domain.user import User


class ISessionRepo(ABC):
    @abstractmethod
    def create(self, session: Session) -> None:
        ...

    @abstractmethod
    def create_workflow(self, workflow: Workflow, session: Session) -> None:
        ...

    @abstractmethod
    def update(self, session: Session) -> None:
        ...

    @abstractmethod
    def update_workflow(self, workflow: Workflow) -> None:
        ...

    @abstractmethod
    def get_session_by_session_id(
        self,
        uuid: SessionId,
        run: int = -1,
        user: User | None = None,
        *,
        permission: Permission | None = None,
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
    def get_runs_for_session(
        self, user: User, uuid: SessionId
    ) -> list[Session]:
        ...

    @abstractmethod
    def get_runs_for_session2(self, user: User, uuid: SessionId) -> list[Run]:
        ...

    @abstractmethod
    def get_recent_sessions_as_admin(self) -> list[Session]:
        """
        Get all recent sessions regardless of who started them. This should
        only be used by people with admin perms, or for testing.
        """

    @abstractmethod
    def can_user_access_session(
        self,
        user: User,
        session: Session,
        *,
        permission: Permission,
    ) -> bool:
        ...

    # TODO: placeholder until a better API comes around
    @abstractmethod
    def get_workflow_id_from_session(
        self, session: Session
    ) -> WorkflowId | None:
        ...
