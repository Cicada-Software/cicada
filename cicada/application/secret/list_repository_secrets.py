from cicada.application.exceptions import NotFound, Unauthorized
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repository import RepositoryId
from cicada.domain.user import User


class ListRepositorySecrets:
    def __init__(
        self,
        repository_repo: IRepositoryRepo,
        secret_repo: ISecretRepo,
    ) -> None:
        self.repository_repo = repository_repo
        self.secret_repo = secret_repo

    def handle(self, user: User, repository_id: RepositoryId) -> list[str]:
        repository = self.repository_repo.get_repository_by_repo_id(repository_id)

        if not repository:
            raise NotFound("Repository not found")

        # TODO: allow admins in addition to owners
        is_owner = self.repository_repo.can_user_access_repo(user, repository, permission="owner")

        if not is_owner:
            raise Unauthorized("You don't have access to this repository")

        return self.secret_repo.list_secrets_for_repo(repository.id)
