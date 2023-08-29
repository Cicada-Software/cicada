import logging

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
        secret_repo: ISecretRepo,
    ) -> None:
        self.repository_repo = repository_repo
        self.secret_repo = secret_repo
        self.logger = logging.getLogger("cicada")

    def handle(self, trigger: Trigger) -> dict[str, str]:
        repo = self.repository_repo.get_repository_by_url_and_provider(
            provider=trigger.provider,
            url=trigger.repository_url,
        )

        if not repo:
            return {}

        repo_info = f"repository id {repo.id}"
        self.logger.info(f"Pulling secrets for {repo_info}")

        secrets = self.secret_repo.get_secrets_for_repo(repo.id)

        count = len(secrets) or "No"
        self.logger.info(f"{count} secrets accessed for {repo_info}")

        return {secret.key: secret.value for secret in secrets}
