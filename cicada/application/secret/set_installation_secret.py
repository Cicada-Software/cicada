import logging

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.domain.installation import InstallationId
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.secret import Secret
from cicada.domain.user import User


class SetInstallationSecret:
    def __init__(
        self,
        installation_repo: IInstallationRepo,
        secret_repo: ISecretRepo,
    ) -> None:
        self.installation_repo = installation_repo
        self.secret_repo = secret_repo
        self.logger = logging.getLogger("cicada")

    def handle(
        self, user: User, installation_id: InstallationId, secret: Secret
    ) -> None:
        installations = self.installation_repo.get_installations_for_user(user)

        for installation in installations:
            if installation.id == installation_id:
                if installation.admin_id != user.id:
                    raise Unauthorized(
                        "You do not have access to this installation"
                    )

                msg = f"User {user.id} is setting env var for installation {installation_id}"  # noqa: E501
                self.logger.info(msg)

                self.secret_repo.set_secrets_for_installation(
                    installation_id, [secret]
                )

                return

        raise NotFound("Installation not found")
