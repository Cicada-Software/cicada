from typing import Any
from uuid import uuid4

from cicada.api.di import DiContainer
from cicada.api.domain.user import User


def update_github_repo_perms(  # type: ignore
    di: DiContainer, event: dict[str, Any]
) -> None:
    match event:
        case {
            "sender": {
                "type": user_type,
                "login": login,
            },
            "repository": {
                "html_url": repo_url,
                "owner": {"login": username},
            },
        } if user_type == "User" and login == username:
            pass

        case _:
            return

    user_repo = di.user_repo()
    repository_repo = di.repository_repo()

    repo = repository_repo.update_or_create_repository(
        url=repo_url, provider="github"
    )

    user_id = user_repo.create_or_update_user(
        User(id=uuid4(), username=username, provider="github")
    )

    repository_repo.update_user_perms_for_repo(repo, user_id, ["owner"])
