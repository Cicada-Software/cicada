from abc import ABC, abstractmethod
from uuid import UUID

from cicada.api.domain.installation import Installation
from cicada.api.domain.user import User


class IInstallationRepo(ABC):
    @abstractmethod
    def create_installation(self, installation: Installation) -> UUID:
        ...

    @abstractmethod
    def get_installations_for_user(self, user: User) -> list[Installation]:
        ...
