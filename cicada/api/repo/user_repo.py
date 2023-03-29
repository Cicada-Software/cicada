from abc import ABC, abstractmethod
from uuid import UUID

from cicada.api.domain.user import User


class IUserRepo(ABC):
    @abstractmethod
    def get_user_by_username(self, username: str) -> User | None:
        pass

    @abstractmethod
    def create_or_update_user(self, user: User) -> UUID:
        pass
