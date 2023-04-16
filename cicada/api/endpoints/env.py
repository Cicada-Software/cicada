from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from cicada.api.application.env.add_env_vars_to_repo import (
    AddEnvironmentVariablesToRepository,
)
from cicada.api.common.json import asjson
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser
from cicada.api.repo.environment_repo import EnvironmentVariable

router = APIRouter()


@dataclass
class EnvVars:
    repository_url: str
    provider: str
    env_vars: dict[str, str]


@router.post("/api/env/repo_env_vars")
def set_repo_env_vars(env_vars: EnvVars, user: CurrentUser, di: Di) -> None:
    cmd = AddEnvironmentVariablesToRepository(
        user_repo=di.user_repo(),
        repository_repo=di.repository_repo(),
        env_repo=di.environment_repo(),
    )

    cmd.handle(
        user.username,
        env_vars.repository_url,
        env_vars.provider,
        [EnvironmentVariable(k, v) for k, v in env_vars.env_vars.items()],
    )


@router.get("/api/env/repo_env_vars")
def get_repo_env_vars(
    user: CurrentUser,
    di: Di,
    provider: Annotated[str, Query()],
    url: Annotated[str, Query()],
) -> JSONResponse:
    # TODO: turn into query command

    repository_repo = di.repository_repo()

    repo = repository_repo.get_repository_by_url_and_provider(
        url=url, provider=provider
    )

    if not repo:
        raise HTTPException(status_code=404)

    if not repository_repo.can_user_see_repo(user, repo):
        # TODO: test
        raise HTTPException(status_code=401)

    return JSONResponse(
        [
            asjson(x)
            for x in di.environment_repo().get_env_vars_for_repo(repo.id)
        ]
    )
