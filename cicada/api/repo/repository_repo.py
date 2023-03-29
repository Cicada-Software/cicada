from abc import ABC, abstractmethod
from typing import Literal
from uuid import UUID

from cicada.api.domain.repository import Repository, RepositoryId
from cicada.api.domain.user import User

# TODO: replace with enum
Permission = Literal["owner"]


class IRepositoryRepo(ABC):
    @abstractmethod
    def get_repository_by_repo_id(self, id: RepositoryId) -> Repository | None:
        ...

    # TODO: is provider needed for lookups?
    @abstractmethod
    def get_repository_by_url_and_provider(
        self, url: str, provider: str
    ) -> Repository | None:
        ...

    @abstractmethod
    def update_or_create_repository(
        self, *, url: str, provider: str
    ) -> Repository:
        ...

    @abstractmethod
    def can_user_see_repo(self, user: User, repo: Repository) -> bool:
        ...

    @abstractmethod
    def update_user_perms_for_repo(
        self, repo: Repository, user: UUID, permissions: list[Permission]
    ) -> None:
        ...
