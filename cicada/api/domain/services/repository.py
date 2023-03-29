from cicada.api.domain.triggers import Trigger
from cicada.api.repo.environment_repo import IEnvironmentRepo
from cicada.api.repo.repository_repo import IRepositoryRepo


def get_env_vars_for_repo(
    env_repo: IEnvironmentRepo,
    repository_repo: IRepositoryRepo,
    trigger: Trigger,
) -> dict[str, str]:
    repo = repository_repo.get_repository_by_url_and_provider(
        provider=trigger.provider,
        url=trigger.repository_url,
    )

    if not repo:
        return {}

    return {
        env.key: env.value for env in env_repo.get_env_vars_for_repo(repo.id)
    }
