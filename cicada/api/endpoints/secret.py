from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter

from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser
from cicada.application.exceptions import InvalidRequest, NotFound
from cicada.application.secret.delete_installation_secret import (
    DeleteInstallationSecret,
)
from cicada.application.secret.delete_repository_secret import (
    DeleteRepositorySecret,
)
from cicada.application.secret.list_installation_secrets import (
    ListInstallationSecrets,
)
from cicada.application.secret.list_repository_secrets import (
    ListRepositorySecrets,
)
from cicada.application.secret.set_installation_secret import (
    SetInstallationSecret,
)
from cicada.application.secret.set_repository_secret import SetRepositorySecret
from cicada.domain.installation import InstallationId
from cicada.domain.secret import Secret

router = APIRouter()


@dataclass
class UpdateSecret:
    scope: Literal["r", "i"]
    key: str
    value: str
    installation_id: InstallationId | None = None

    # TODO: use repository UUID on frontend
    repository_url: str | None = None
    repository_provider: str | None = None


@dataclass
class DeleteSecret:
    scope: Literal["r", "i"]
    key: str
    installation_id: InstallationId | None = None

    # TODO: use repository UUID on frontend
    repository_url: str | None = None
    repository_provider: str | None = None


@router.put("/api/secret")
async def update_secret(
    di: Di, user: CurrentUser, secret: UpdateSecret
) -> None:
    if secret.scope == "r":
        # TODO: move validation to dataclass

        if not secret.repository_url:
            raise InvalidRequest("Expected repository url")

        if not secret.repository_provider:
            raise InvalidRequest("Expected repository provider")

        # TODO: switch to repository uuid instead of url+provider combo
        repository_repo = di.repository_repo()

        repository = repository_repo.get_repository_by_url_and_provider(
            secret.repository_url,
            secret.repository_provider,
        )

        if not repository:
            raise NotFound("Could not find repository")

        cmd = SetRepositorySecret(repository_repo, di.secret_repo())

        cmd.handle(user, repository.id, Secret(secret.key, secret.value))

    else:
        if not secret.installation_id:
            raise InvalidRequest("Expected installation id")

        cmd = SetInstallationSecret(  # type: ignore
            di.installation_repo(), di.secret_repo()
        )

        cmd.handle(
            user,
            secret.installation_id,  # type: ignore
            Secret(secret.key, secret.value),
        )


@router.get("/api/secret/repository")
async def list_secrets_for_repo(
    di: Di,
    user: CurrentUser,
    url: str,
    provider: str,
) -> list[str]:
    # TODO: use repository uuid

    repository_repo = di.repository_repo()

    repository = repository_repo.get_repository_by_url_and_provider(
        url,
        provider,
    )

    if not repository:
        raise NotFound("Could not find repository")

    cmd = ListRepositorySecrets(repository_repo, di.secret_repo())

    return cmd.handle(user, repository.id)


@router.get("/api/secret/installation/{uuid}")
async def list_secrets_for_installation(
    di: Di,
    user: CurrentUser,
    uuid: InstallationId,
) -> list[str]:
    cmd = ListInstallationSecrets(di.installation_repo(), di.secret_repo())

    return cmd.handle(user, uuid)


@router.delete("/api/secret")
async def delete_secret(
    di: Di,
    user: CurrentUser,
    secret: DeleteSecret,
) -> None:
    if secret.scope == "r":
        if not (secret.repository_provider and secret.repository_url):
            raise InvalidRequest("repository provider and url must be passed")

        repository_repo = di.repository_repo()

        repo = repository_repo.get_repository_by_url_and_provider(
            secret.repository_url,
            secret.repository_provider,
        )

        if not repo:
            raise NotFound("Repository not found")

        cmd = DeleteRepositorySecret(repository_repo, di.secret_repo())

        cmd.handle(user, repo.id, secret.key)

    else:
        if not secret.installation_id:
            raise InvalidRequest("installation id must be set")

        cmd = DeleteInstallationSecret(  # type: ignore
            di.installation_repo(), di.secret_repo()
        )

        cmd.handle(user, secret.installation_id, secret.key)  # type: ignore
