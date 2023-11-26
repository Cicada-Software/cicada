import logging

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repository import RepositoryId
from cicada.domain.secret import Secret
from cicada.domain.user import User


class SetRepositorySecret:
    def __init__(
        self,
        repository_repo: IRepositoryRepo,
        secret_repo: ISecretRepo,
    ) -> None:
        self.repository_repo = repository_repo
        self.secret_repo = secret_repo
        self.logger = logging.getLogger("cicada")

    def handle(
        self,
        user: User,
        repository_id: RepositoryId,
        secret: Secret,
    ) -> None:
        repository = self.repository_repo.get_repository_by_repo_id(repository_id)

        if not repository:
            raise NotFound("Repository not found")

        is_owner = self.repository_repo.can_user_access_repo(user, repository, permission="owner")

        if not is_owner:
            raise Unauthorized("You are not authorized to view this repository")

        self.logger.info("User %s is setting env var for repository %s", user.id, repository.id)

        self.secret_repo.set_secrets_for_repo(repository.id, [secret])
