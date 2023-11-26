import logging

from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.triggers import Trigger


class GatherSecretsFromTrigger:
    """
    Get all repository and installation scoped secrets that can be accessed by
    this trigger. Repository scoped secrets take precedence over installation
    scoped secrets if both are defined.

    This service will log when secrets are being accessed, and after the
    secrets have been received, the number of secrets that where accessed is
    logged as well.

    Do not call the underlying secret repository, use this service instead.
    """

    def __init__(
        self,
        repository_repo: IRepositoryRepo,
        installation_repo: IInstallationRepo,
        secret_repo: ISecretRepo,
    ) -> None:
        self.repository_repo = repository_repo
        self.installation_repo = installation_repo
        self.secret_repo = secret_repo
        self.logger = logging.getLogger("cicada")

    def handle(self, trigger: Trigger) -> dict[str, str]:
        repo = self.repository_repo.get_repository_by_url_and_provider(
            provider=trigger.provider,
            url=trigger.repository_url,
        )

        if not repo:
            return {}

        # TODO: should installation always be required?
        installation_id = self.installation_repo.get_installation_id_by_repository_id(repo.id)

        output: dict[str, str] = {}

        if installation_id:
            # TODO: isolate shared logging logic
            self.logger.info("Pulling secrets for installation id %s", installation_id)

            secrets = self.secret_repo.get_secrets_for_installation(installation_id)

            count = len(secrets) or "No"
            self.logger.info("%s secrets accessed for installation id %s", count, installation_id)

            output = {secret.key: secret.value for secret in secrets}

        self.logger.info("Pulling secrets for repository id %s", repo.id)

        secrets = self.secret_repo.get_secrets_for_repo(repo.id)

        count = len(secrets) or "No"
        self.logger.info("%s secrets accessed for repository id %s", count, repo.id)

        # Override installation secrets (if any) with repository secrets
        for secret in secrets:
            output[secret.key] = secret.value

        return output
