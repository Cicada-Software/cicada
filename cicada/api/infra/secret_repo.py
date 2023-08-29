from cicada.domain.installation import InstallationId
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repository import RepositoryId
from cicada.domain.secret import Secret


# TODO: implement
class SecretRepo(ISecretRepo):
    def get_secrets_for_repo(self, id: RepositoryId) -> list[Secret]:
        return []

    def get_secrets_for_installation(self, id: InstallationId) -> list[Secret]:
        return []

    def set_secrets_for_repo(
        self, id: RepositoryId, secrets: list[Secret]
    ) -> None:
        pass

    def set_secrets_for_installation(
        self, id: InstallationId, secrets: list[Secret]
    ) -> None:
        pass
