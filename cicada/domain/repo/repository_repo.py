from abc import ABC, abstractmethod
from typing import Literal

from cicada.domain.repository import Repository, RepositoryId
from cicada.domain.user import User, UserId

# TODO: replace with enum
Permission = Literal["owner", "read", "write"]


class IRepositoryRepo(ABC):
    @abstractmethod
    def get_repository_by_repo_id(self, id: RepositoryId) -> Repository | None:
        ...

    # TODO: is provider needed for lookups?
    @abstractmethod
    def get_repository_by_url_and_provider(self, url: str, provider: str) -> Repository | None:
        ...

    @abstractmethod
    def update_or_create_repository(
        self, *, url: str, provider: str, is_public: bool
    ) -> Repository:
        ...

    @abstractmethod
    def can_user_access_repo(
        self,
        user: User,
        repo: Repository,
        *,
        permission: Permission = "owner",
    ) -> bool:
        ...

    @abstractmethod
    def update_user_perms_for_repo(
        self, repo: Repository, user: UserId, permissions: list[Permission]
    ) -> None:
        ...
