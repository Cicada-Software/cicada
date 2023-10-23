from typing import Any
from uuid import uuid4

from cicada.api.di import DiContainer
from cicada.domain.user import User


def update_gitlab_repo_perms(di: DiContainer, event: dict[str, Any]) -> None:  # type: ignore[misc]
    match event:
        case {
            "object_kind": "issue",
            "user": {"username": username},
            "project": {
                "namespace": namespace,
                "web_url": repo_url,
            },
        } if username == namespace:
            pass

        case {
            "object_kind": "push",
            "user_name": username,
            "project": {
                "namespace": namespace,
                "web_url": repo_url,
            },
        } if username == namespace:
            pass

        case _:
            return

    user_repo = di.user_repo()
    repository_repo = di.repository_repo()

    # TODO: check if repo is public/private
    repo = repository_repo.update_or_create_repository(
        url=repo_url,
        provider="gitlab",
        is_public=False,
    )

    user_id = user_repo.create_or_update_user(
        User(id=uuid4(), username=username, provider="gitlab")
    )

    repository_repo.update_user_perms_for_repo(repo, user_id, ["owner"])
