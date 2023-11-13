from urllib.parse import quote as url_escape
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from gitlab import Gitlab

from cicada.api.di import DiContainer
from cicada.api.endpoints.csrf import CsrfTokenCache
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import create_jwt
from cicada.api.settings import DNSSettings, GitlabSettings
from cicada.domain.user import User

router = APIRouter()


CSRF_TOKENS = CsrfTokenCache()


def get_gitlab_sso_link(url: str | None = None) -> str:
    settings = GitlabSettings()

    redirect_uri = f"https://{settings.domain}/api/gitlab_sso"

    url = url_escape(f"{redirect_uri}?url={url}" if url else redirect_uri)

    # TODO: use an actual URL constructor instead
    params = {
        "state": CSRF_TOKENS.generate(),
        "client_id": settings.client_id,
        "response_type": "code",
        "scope": "api",
        "redirect_uri": url,
    }

    url_params = "&".join(f"{key}={value}" for key, value in params.items())

    return f"https://gitlab.com/oauth/authorize?{url_params}"


@router.get("/api/gitlab_sso_link")
async def gitlab_sso_link(url: str | None = None) -> RedirectResponse:
    return RedirectResponse(get_gitlab_sso_link(url), status_code=302)


@router.get("/api/gitlab_sso")
async def gitlab_sso(
    di: Di,
    code: str,
    state: str,
    url: str | None = None,
) -> HTMLResponse:  # pragma: no cover
    CSRF_TOKENS.validate(state)

    settings = DNSSettings()

    if url and not url.startswith((f"https://{settings.domain}/", "/")):
        raise HTTPException(400, f"URL must start with `https://{settings.domain}/` or `/`")

    # TODO: if "setup_action" query param is set to "install" redirect user to
    # docs/setup/onboarding info.

    jwt = await generate_jwt_from_gitlab_sso(di, code)

    url = url or "/dashboard"

    return HTMLResponse(
        f"""\
<!DOCTYPE html>
<html>
<head>
<title>You are being redirected</title>
<script src="/static/common.js"></script>
</head>
<body>
<script>
setKey("jwt", "{jwt}");

window.location.href = decodeURI("{url}");
</script>
</body>
</html>
"""
    )


async def generate_jwt_from_gitlab_sso(di: DiContainer, code: str) -> str:
    settings = GitlabSettings()

    params = {
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.redirect_uri,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post("https://gitlab.com/oauth/token", params=params)

    data = resp.json()

    token_store = di.gitlab_token_store()
    token = token_store.oauth_response_to_token(data)

    gl = Gitlab(oauth_token=token.access_token)
    gl.auth()

    assert gl.user

    attrs = gl.user.asdict()

    username = attrs["username"]
    email = attrs["email"]

    new_gitlab_user = User(
        id=uuid4(),
        username=username,
        email=email,
        provider="gitlab",
    )

    user_repo = di.user_repo()

    new_gitlab_user.id = user_repo.create_or_update_user(new_gitlab_user)

    user_repo.update_last_login(new_gitlab_user)

    token_store.save_token(new_gitlab_user, token)

    return create_jwt(subject=username, issuer="gitlab")
