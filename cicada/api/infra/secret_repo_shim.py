from cicada.domain.installation import InstallationId
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repository import RepositoryId
from cicada.domain.secret import Secret


class SecretRepoShim(ISecretRepo):
    def list_secrets_for_repo(self, id: RepositoryId) -> list[str]:
        return []

    def list_secrets_for_installation(self, id: InstallationId) -> list[str]:
        return []

    def get_secrets_for_repo(self, id: RepositoryId) -> list[Secret]:
        return []

    def get_secrets_for_installation(self, id: InstallationId) -> list[Secret]:
        return []

    def set_secrets_for_repo(
        self, id: RepositoryId, secrets: list[Secret]
    ) -> None:
        ...

    def set_secrets_for_installation(
        self, id: InstallationId, secrets: list[Secret]
    ) -> None:
        ...

    def delete_repository_secret(self, id: RepositoryId, key: str) -> None:
        ...

    def delete_installation_secret(self, id: InstallationId, key: str) -> None:
        ...
