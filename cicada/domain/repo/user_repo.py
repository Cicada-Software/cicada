from abc import ABC, abstractmethod

from cicada.domain.user import User, UserId


class IUserRepo(ABC):
    @abstractmethod
    def get_user_by_username(self, username: str) -> User | None:
        pass

    @abstractmethod
    def create_or_update_user(self, user: User) -> UserId:
        pass

    @abstractmethod
    def update_last_login(self, user: User) -> None:
        pass
