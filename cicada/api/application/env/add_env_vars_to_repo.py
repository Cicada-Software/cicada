from cicada.api.application.exceptions import NotFound, Unauthorized
from cicada.api.repo.environment_repo import (
    EnvironmentVariable,
    IEnvironmentRepo,
)
from cicada.api.repo.repository_repo import IRepositoryRepo
from cicada.api.repo.user_repo import IUserRepo


class AddEnvironmentVariablesToRepository:
    """
    Add/update a list of environment variables attached to a repository. The
    list of env vars passed to this service overrides whatever env vars already
    might exist, or in other words, calling this service will replace all
    repo-scoped env vars with the new list.

    If the user/repo doesnt exist, or the user does not have sufficient
    permissions to the repo (currently "owner" is needed), nothing will happen.
    """

    def __init__(
        self,
        user_repo: IUserRepo,
        repository_repo: IRepositoryRepo,
        env_repo: IEnvironmentRepo,
    ) -> None:
        self.user_repo = user_repo
        self.repository_repo = repository_repo
        self.env_repo = env_repo

    # TODO: use user id instead of platform-dependant username
    def handle(
        self,
        username: str,
        repo_url: str,
        provider: str,
        env_vars: list[EnvironmentVariable],
    ) -> None:
        user = self.user_repo.get_user_by_username(username)

        if not user:
            raise NotFound("User not found")

        repo = self.repository_repo.get_repository_by_url_and_provider(
            repo_url, provider
        )

        if not repo:
            raise NotFound(f"Repository {repo_url} not found")

        if not self.repository_repo.can_user_see_repo(user, repo):
            raise Unauthorized("User is not allowed to modify env vars")

        self.env_repo.set_env_vars_for_repo(repo.id, env_vars)
