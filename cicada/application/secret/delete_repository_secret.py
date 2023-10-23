import logging

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repository import RepositoryId
from cicada.domain.user import User


class DeleteRepositorySecret:
    def __init__(
        self,
        repository_repo: IRepositoryRepo,
        secret_repo: ISecretRepo,
    ) -> None:
        self.repository_repo = repository_repo
        self.secret_repo = secret_repo
        self.logger = logging.getLogger("cicada")

    def handle(self, user: User, id: RepositoryId, key: str) -> None:
        repo = self.repository_repo.get_repository_by_repo_id(id)

        if not repo:
            raise NotFound("Repository not found")

        # TODO: allow non owners (ie admins) to delete as well
        is_owner = self.repository_repo.can_user_access_repo(user, repo, permission="owner")

        if not is_owner:
            raise Unauthorized("You are not allowed to delete repository secrets")

        self.logger.info(f"User {user.id} deleting secret for repository id {repo.id}")
        self.secret_repo.delete_repository_secret(id, key)
