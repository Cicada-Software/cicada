from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse

from cicada.api.endpoints.di import Di, JWTToken, PasswordForm
from cicada.application.user.change_password import ChangePassword
from cicada.application.user.local_user_login import LocalUserLogin

from .login_util import (
    CurrentUser,
    create_access_token,
    get_user_and_payload_from_jwt,
)

router = APIRouter()


@router.post("/api/login", response_model=None)
async def login(  # type: ignore[misc]
    di: Di,
    form_data: PasswordForm,
) -> dict[str, Any]:
    cmd = LocalUserLogin(di.user_repo())
    user = cmd.handle(form_data.username, form_data.password)

    return create_access_token(user)


@router.post("/api/change_password")
async def change_password(
    user: CurrentUser,
    di: Di,
    password: Annotated[str, Form()] = "",
) -> None:
    cmd = ChangePassword(di.user_repo())

    cmd.handle(user, password)


@router.post("/api/refresh_token")
async def refresh_token(  # type: ignore[misc]
    di: Di,
    token: JWTToken,
) -> dict[str, Any]:
    if data := get_user_and_payload_from_jwt(di.user_repo(), token):
        user, payload = data

        return create_access_token(user, issuer=payload["iss"])

    raise HTTPException(
        status_code=401,
        detail="JWT Invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/login")
def login_page() -> FileResponse:
    return FileResponse("./frontend/login.html")
