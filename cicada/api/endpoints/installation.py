from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from cicada.api.application.exceptions import NotFound
from cicada.api.common.json import asjson
from cicada.api.domain.installation import Installation
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser

router = APIRouter()


def InstallationDto(installation: Installation) -> dict[str, Any]:  # type: ignore
    data = asjson(installation)
    del data["admin_id"]

    return data  # type: ignore


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
    uuid: UUID,
) -> JSONResponse:
    installations = di.installation_repo().get_installations_for_user(user)

    for installation in installations:
        if installation.id == uuid:
            return JSONResponse(InstallationDto(installation))

    raise NotFound("Installation not found")
