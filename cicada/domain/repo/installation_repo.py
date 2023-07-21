from abc import ABC, abstractmethod

from cicada.domain.installation import Installation, InstallationId
from cicada.domain.repository import Repository
from cicada.domain.user import User


class IInstallationRepo(ABC):
    @abstractmethod
    def create_or_update_installation(
        self, installation: Installation
    ) -> InstallationId:
        ...

    @abstractmethod
    def get_installations_for_user(self, user: User) -> list[Installation]:
        ...

    @abstractmethod
    def get_installation_by_provider_id(
        self, *, id: str, provider: str
    ) -> Installation | None:
        ...

    @abstractmethod
    def add_repository_to_installation(
        self, repo: Repository, installation: Installation
    ) -> None:
        ...
