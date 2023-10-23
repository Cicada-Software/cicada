from contextlib import suppress
from functools import cache
from urllib.parse import quote as url_escape
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from githubkit import GitHub, OAuthWebAuthStrategy, TokenAuthStrategy

from cicada.api.di import DiContainer
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import create_jwt
from cicada.api.infra.github.common import get_github_integration
from cicada.api.settings import GitHubSettings
from cicada.domain.user import User

router = APIRouter()


@cache
def get_github_sso_link(url: str | None = None) -> str:
    settings = GitHubSettings()

    url = url_escape(
        f"{settings.sso_redirect_uri}?url={url}" if url else settings.sso_redirect_uri
    )

    # TODO: use an actual URL constructor instead
    params = {
        "state": "state",
        "allow_signup": "false",
        "client_id": settings.client_id,
        "redirect_uri": url,
    }

    url_params = "&".join(f"{key}={value}" for key, value in params.items())

    return f"https://github.com/login/oauth/authorize?{url_params}"


@cache
def get_github_app_install_link() -> str:
    github = get_github_integration()

    # Use synchronous version because this is only ran once then cached, and
    # using the async version requires manually caching the result which was
    # too much extra work.
    resp = github.rest.apps.get_authenticated()

    return f"{resp.parsed_data.html_url}/installations/new"


@router.get("/api/github_sso_link")
async def github_sso_link(url: str | None = None) -> RedirectResponse:
    return RedirectResponse(get_github_sso_link(url), status_code=302)


@router.get("/api/github_app_install_link")
async def github_app_install_link() -> RedirectResponse:
    return RedirectResponse(get_github_app_install_link(), status_code=302)


@router.get("/api/github_sso")
async def github_sso(
    di: Di,
    code: str,
    url: str | None = None,
) -> HTMLResponse:  # pragma: no cover
    # TODO: if "setup_action" query param is set to "install" redirect user to
    # docs/setup/onboarding info.

    jwt = await generate_jwt_from_github_sso(di, code)

    url = url or "/dashboard"

    # TODO: set this via cookie instead of doing SSR?
    # TODO: add "from" field to direct user to where they came from
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


async def generate_jwt_from_github_sso(di: DiContainer, code: str) -> str:
    settings = GitHubSettings()

    github = GitHub(
        OAuthWebAuthStrategy(
            settings.client_id,
            settings.client_secret,
            code,
        )
    )

    # TODO: use githubkit to exchange token
    resp = await github.arequest(  # type: ignore
        url="https://github.com/login/oauth/access_token",
        method="post",
        params={
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "code": code,
        },
        headers={"Accept": "application/json"},
    )

    github = GitHub(TokenAuthStrategy(resp.json()["access_token"]))

    email: str | None = None

    # Ignore exceptions since email permissions might not be setup for GitHub
    # app, or email might not be set (for some reason).
    with suppress(Exception):
        resp = await github.rest.users.async_list_emails_for_authenticated_user()
        email = next(email.email for email in resp.parsed_data if email.primary)

    # TODO: run these in parallel
    user = await github.rest.users.async_get_authenticated()
    username = user.parsed_data.login

    new_github_user = User(
        id=uuid4(),
        username=username,
        email=email,
        provider="github",
    )

    user_repo = di.user_repo()

    new_github_user.id = user_repo.create_or_update_user(new_github_user)

    user_repo.update_last_login(new_github_user)

    return create_jwt(subject=username, issuer="github")
