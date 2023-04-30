from abc import ABC, abstractmethod

from cicada.api.domain.installation import Installation, InstallationId
from cicada.api.domain.user import User


class IInstallationRepo(ABC):
    @abstractmethod
    def create_installation(
        self, installation: Installation
    ) -> InstallationId:
        ...

    @abstractmethod
    def get_installations_for_user(self, user: User) -> list[Installation]:
        ...
