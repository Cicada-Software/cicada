from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser
from cicada.application.exceptions import NotFound
from cicada.common.json import asjson
from cicada.domain.installation import Installation, InstallationId

router = APIRouter()


def InstallationDto(  # type: ignore[misc]  # noqa: N802
    installation: Installation,
) -> dict[str, Any]:
    data = asjson(installation)
    del data["admin_id"]

    return data  # type: ignore[no-any-return]


@router.get("/api/installations")
def get_installations_for_current_user(
    user: CurrentUser,
    di: Di,
) -> JSONResponse:
    installations = di.installation_repo().get_installations_for_user(user)

    return JSONResponse([InstallationDto(x) for x in installations])


@router.get("/api/installation/{uuid}")
def get_installation_by_id(
    user: CurrentUser,
    di: Di,
    uuid: InstallationId,
) -> JSONResponse:
    installations = di.installation_repo().get_installations_for_user(user)

    for installation in installations:
        if installation.id == uuid:
            return JSONResponse(InstallationDto(installation))

    raise NotFound("Installation not found")
