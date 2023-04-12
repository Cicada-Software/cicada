from typing import Any
from uuid import UUID, uuid4

from cicada.api.di import DiContainer
from cicada.api.domain.installation import Installation, InstallationScope
from cicada.api.domain.user import User
from cicada.api.repo.user_repo import IUserRepo


def create_or_update_github_user(  # type: ignore
    user_repo: IUserRepo, event: dict[str, Any]
) -> User | None:
    match event:
        case {"sender": {"type": "User", "login": sender_username}}:
            user = User(
                id=uuid4(), username=sender_username, provider="github"
            )
            user.id = user_repo.create_or_update_user(user)

            return user

    return None


def update_github_repo_perms(  # type: ignore
    di: DiContainer,
    user_id: UUID,
    event: dict[str, Any],
    event_type: str,
) -> None:
    """
    Determine a user's permissions for a given repository based soley on the
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
            },
        }:
            if sender_username == repository_owner_username:
                perms = "owner"
            elif event_type == "push":
                perms = "write"
            elif event_type == "issues":
                perms = "read"
            else:
                return

        case _:
            return

    repository_repo = di.repository_repo()

    repo = repository_repo.update_or_create_repository(
        url=repo_url, provider="github"
    )

    repository_repo.update_user_perms_for_repo(
        repo, user_id, [perms]  # type: ignore
    )


def create_or_update_github_installation(  # type: ignore
    di: DiContainer, user_id: UUID, event: dict[str, Any]
) -> None:
    match event:
        case {
            "action": "added" | "created",
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

            repo.create_installation(installation)

        case _:
            return
