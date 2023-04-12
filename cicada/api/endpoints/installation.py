from __future__ import annotations

from dataclasses import asdict, dataclass

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from cicada.api.domain.installation import Installation
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser

router = APIRouter()


@dataclass
class InstallationDTO:
    name: str
    provider: str
    scope: str

    @classmethod
    def from_installation(cls, installation: Installation) -> InstallationDTO:
        return cls(
            name=installation.name,
            provider=installation.provider,
            scope=str(installation.scope),
        )


@router.get("/installations")
def get_installations_for_current_user(
    user: CurrentUser,
    di: Di,
) -> JSONResponse:
    installations = di.installation_repo().get_installations_for_user(user)

    return JSONResponse(
        [asdict(InstallationDTO.from_installation(x)) for x in installations]
    )
