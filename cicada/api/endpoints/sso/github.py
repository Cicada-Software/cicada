from functools import cache
from urllib.parse import quote as url_escape
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from githubkit import GitHub, OAuthWebAuthStrategy

from cicada.api.di import DiContainer
from cicada.api.domain.user import User
from cicada.api.endpoints.di import Di
from cicada.api.settings import GitHubSettings

from ..login_util import create_jwt

router = APIRouter()


@cache
def get_github_sso_link() -> str:
    settings = GitHubSettings()

    # TODO: use an actual URL constructor instead
    params = {
        "state": "state",
        "allow_signup": "false",
        "client_id": settings.client_id,
        "redirect_uri": url_escape(settings.sso_redirect_uri),
    }

    url_params = "&".join(f"{key}={value}" for key, value in params.items())

    return f"https://github.com/login/oauth/authorize?{url_params}"


@router.get("/api/github_sso_link")
async def github_sso_link() -> RedirectResponse:
    return RedirectResponse(get_github_sso_link(), status_code=302)


@router.get("/api/github_sso")
async def github_sso(di: Di, code: str) -> HTMLResponse:  # pragma: no cover
    # TODO: if "setup_action" query param is set to "install" redirect user to
    # docs/setup/onboarding info.

    jwt = await generate_jwt_from_github_sso(di, code)

    # TODO: set this via cookie instead of doing SSR?
    # TODO: add "from" field to direct user to where they came from
    return HTMLResponse(
        f"""\
<!DOCTYPE html>
<html>
<head><title>You are being redirected</title></head>
<body>
<script>
localStorage.setItem("jwt", "{jwt}");

window.location.href = "/dashboard";
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

    user = await github.rest.users.async_get_authenticated()
    username = user.parsed_data.login

    new_github_user = User(id=uuid4(), username=username, provider="github")

    user_repo = di.user_repo()

    new_github_user.id = user_repo.create_or_update_user(new_github_user)

    user_repo.update_last_login(new_github_user)

    return create_jwt(subject=username, issuer="github")
