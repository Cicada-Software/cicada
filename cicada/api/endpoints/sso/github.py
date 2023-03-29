from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from githubkit import GitHub, OAuthWebAuthStrategy

from cicada.api.di import DiContainer
from cicada.api.domain.user import User
from cicada.api.endpoints.di import Di
from cicada.api.settings import GitHubSettings

from ..login_util import create_jwt

router = APIRouter()


@router.get("/github_sso")
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

    di.user_repo().create_or_update_user(new_github_user)

    return create_jwt(subject=username, issuer="github")
