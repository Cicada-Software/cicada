from abc import ABC, abstractmethod

from cicada.domain.installation import InstallationId
from cicada.domain.repository import RepositoryId
from cicada.domain.secret import Secret


class ISecretRepo(ABC):
    """
    API for accessing secrets. This API will not log access via these methods,
    users should use the respective application services which will validate
    users and log user access.
    """

    @abstractmethod
    def list_secrets_for_repo(self, id: RepositoryId) -> list[str]:
        """
        List only the key, not the values, of secrets for a specific
        repository. This is much faster (and more secure) if you only care
        about the names of the keys but not the values.
        """

    @abstractmethod
    def list_secrets_for_installation(self, id: InstallationId) -> list[str]:
        """
        Same as list_secrets_for_repo, but for installations.
        """

    @abstractmethod
    def get_secrets_for_repo(self, id: RepositoryId) -> list[Secret]:
        """
        Get a list of secrets that have been set for a given repository. This
        will only return env vars set for this repo, it will not include env
        vars that are available for the whole installation.
        """

        ...

    @abstractmethod
    def get_secrets_for_installation(self, id: InstallationId) -> list[Secret]:
        """
        Get a list of secrets that are set for the installation. It will not
        include all secrets for the whole installation, only secrets which are
        available installation wide.
        """

        ...

    @abstractmethod
    def set_secrets_for_repo(self, id: RepositoryId, secrets: list[Secret]) -> None:
        ...

    @abstractmethod
    def set_secrets_for_installation(self, id: InstallationId, secrets: list[Secret]) -> None:
        ...

    @abstractmethod
    def delete_repository_secret(self, id: RepositoryId, key: str) -> None:
        """
        Delete a given repository secret (if it exists).
        """

        ...

    @abstractmethod
    def delete_installation_secret(self, id: InstallationId, key: str) -> None:
        """
        Delete a given installation secret (if it exists).
        """

        ...
