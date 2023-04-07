# TODO: move this to an infra folder

from unittest.mock import AsyncMock, patch

import pytest

from cicada.api.endpoints.login_util import get_user_and_payload_from_jwt
from cicada.api.endpoints.sso.github import generate_jwt_from_github_sso
from test.api.endpoints.common import TestEndpointWrapper


class FakeOAuthResponse:
    def json(self) -> dict[str, str]:
        return {"access_token": "jwt_token"}


class FakeGitHubUserResponse:
    def json(self) -> dict[str, str]:
        return {"login": "github_username"}


class FakeUser:
    username: str = "github_username"


class TestGithubSSO(TestEndpointWrapper):
    @pytest.mark.skip("Can't get the mock to work properly")
    async def test_github_sso_login_creates_new_user(self) -> None:
        with (
            self.inject_dummy_env_vars(),
            patch("githubkit.GitHub") as github_mock,
        ):
            github_mock.rest.users.async_get_authenticated = AsyncMock(
                return_value=FakeUser()
            )

            jwt = await generate_jwt_from_github_sso(code="abc132", di=self.di)

            data = get_user_and_payload_from_jwt(self.di.user_repo(), jwt)
            assert data

            user, _ = data

            assert user.username == "github_username"
            assert not user.password_hash
            assert not user.is_admin

            got_user = self.di.user_repo().get_user_by_username(
                "github_username"
            )

            assert got_user
            assert got_user.username == "github_username"
            assert got_user.last_login
