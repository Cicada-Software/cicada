from typing import Any
from uuid import uuid4

from cicada.api.di import DiContainer
from cicada.domain.installation import Installation, InstallationScope
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.user_repo import IUserRepo
from cicada.domain.repository import Repository
from cicada.domain.user import User, UserId


def create_or_update_github_user(  # type: ignore[misc]
    user_repo: IUserRepo, event: dict[str, Any]
) -> User | None:
    match event:
        case {"sender": {"type": "User", "login": sender_username}}:
            user = User(id=uuid4(), username=sender_username, provider="github")

            user_id = user_repo.create_or_update_user(user)

            return user_repo.get_user_by_id(user_id)

    return None


def update_github_repo_perms(  # type: ignore[misc]
    di: DiContainer,
    user_id: UserId,
    event: dict[str, Any],
    event_type: str,
) -> Repository | None:
    """
    Determine a user's permissions for a given repository based solely on the
    data in the webhook. GitHub's API doesn't provide a succinct way to query
    what permissions a user has for a given repository, so this will do for
    now. Basically, if we get a webhook saying a user did a certain thing, we
    should be safe to assume the user has at least some permissions on GitHUb
    to be able to carry out that action. For example, if a user is able to
    push code to a repository, we can assume that they have at least write
    permission.

    The only issue with this design is that if a user has a certain permission
    level which is later revoked on GitHub's side of things, this change will
    not be reflected on Cicada. The end goal would be to replace this function
    with an API call that will check a user's permissions for every event that
    is triggered.

    Currently, here is how permissions are determined:

    * If the sender username matches the repository owner username, the Cicada
      user will have "owner" permissions on the repository.

    * If the event is a push event, the user will have "write" permissions.

    * If the event is an issue event, the user will have "read" permissions.
    """

    match event:
        case {
            "sender": {
                "type": "User",
                "login": sender_username,
            },
            "repository": {
                "html_url": repo_url,
                "owner": {"login": repository_owner_username},
                "private": is_private,
            },
        }:
            if sender_username == repository_owner_username:
                perms = "owner"
            elif event_type == "push":
                perms = "write"
            elif event_type == "issues":
                perms = "read"
            else:
                return None

        case _:
            return None

    repository_repo = di.repository_repo()

    repo = repository_repo.update_or_create_repository(
        url=repo_url,
        provider="github",
        is_public=not is_private,
    )

    repository_repo.update_user_perms_for_repo(repo, user_id, [perms])  # type: ignore[list-item]

    return repository_repo.get_repository_by_repo_id(repo.id)


def create_or_update_github_installation(  # type: ignore[misc]
    di: DiContainer, user_id: UserId, event: dict[str, Any]
) -> Installation | None:
    match event:
        case {
            "action": "added" | "created" | "removed",
            "installation": {
                "account": {"login": str(name)},
                "target_type": "User" | "Organization" as target_type,
                "html_url": str(url),
                "id": installation_id,
            },
        }:
            installation = Installation(
                id=uuid4(),
                name=name,
                provider="github",
                scope=(
                    InstallationScope.USER
                    if target_type == "User"
                    else InstallationScope.ORGANIZATION
                ),
                admin_id=user_id,
                provider_id=str(installation_id),
                provider_url=url,
            )

            repo = di.installation_repo()

            repo.create_or_update_installation(installation)

            return installation

    return None


# TODO: test this
def add_repository_to_installation(  # type: ignore[misc]
    installation_repo: IInstallationRepo,
    repository: Repository,
    event: dict[str, Any],
) -> None:
    match event:
        case {"installation": {"id": int(installation_id)}}:
            installation = installation_repo.get_installation_by_provider_id(
                id=str(installation_id),
                provider="github",
            )

            if installation and repository:
                installation_repo.add_repository_to_installation(repository, installation)
