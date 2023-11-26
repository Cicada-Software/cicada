import logging

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.domain.installation import InstallationId
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.user import User


class DeleteInstallationSecret:
    def __init__(
        self,
        installation_repo: IInstallationRepo,
        secret_repo: ISecretRepo,
    ) -> None:
        self.installation_repo = installation_repo
        self.secret_repo = secret_repo
        self.logger = logging.getLogger("cicada")

    def handle(self, user: User, id: InstallationId, key: str) -> None:
        installations = self.installation_repo.get_installations_for_user(user)

        for installation in installations:
            if installation.id == id:
                if installation.admin_id != user.id:
                    raise Unauthorized("You do not have access to this installation")

                self.logger.info(
                    "User %s deleting secret for installation %s", user.id, installation.id
                )

                self.secret_repo.delete_installation_secret(id, key)

                return

        raise NotFound("Installation not found")
