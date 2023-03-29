from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import quote as url_escape

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse

from cicada.api.application.user.change_password import ChangePassword
from cicada.api.endpoints.di import Di, JWTToken, PasswordForm
from cicada.api.settings import GitHubSettings

from .login_util import (
    CurrentUser,
    authenticate_user,
    create_access_token,
    get_user_and_payload_from_jwt,
)

router = APIRouter()


@router.post("/login", response_model=None)
async def login(  # type: ignore
    di: Di,
    form_data: PasswordForm,
) -> dict[str, Any]:
    user = authenticate_user(
        di.user_repo(), form_data.username, form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return create_access_token(user)


@router.post("/change_password")
async def change_password(
    user: CurrentUser,
    di: Di,
    password: str = Form(""),
) -> None:
    cmd = ChangePassword(di.user_repo())

    cmd.handle(user, password)


@router.post("/refresh_token")
async def refresh_token(  # type: ignore
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


@cache
def get_login_page() -> str:
    settings = GitHubSettings()

    return (
        Path("frontend/login.html")
        .read_text()
        .replace("CLIENT_ID", settings.client_id)
        .replace("REDIRECT_URI", url_escape(settings.sso_redirect_uri))
    )


@router.get("/login")
def login_page() -> HTMLResponse:
    return HTMLResponse(get_login_page())
