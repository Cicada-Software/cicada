from cicada.application.exceptions import NotFound, Unauthorized
from cicada.domain.installation import InstallationId
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.user import User


class ListInstallationSecrets:
    def __init__(
        self,
        installation_repo: IInstallationRepo,
        secret_repo: ISecretRepo,
    ) -> None:
        self.installation_repo = installation_repo
        self.secret_repo = secret_repo

    def handle(self, user: User, installation_id: InstallationId) -> list[str]:
        installations = self.installation_repo.get_installations_for_user(user)

        for installation in installations:
            if installation.id == installation_id:
                if installation.admin_id != user.id:
                    raise Unauthorized(
                        "You are not authorized to this installation"
                    )

                return self.secret_repo.list_secrets_for_installation(
                    installation_id
                )

        raise NotFound("Installation not found")
