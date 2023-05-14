from unittest.mock import MagicMock

from cicada.api.common.datetime import UtcDatetime
from cicada.api.domain.user import User
from cicada.api.endpoints.login_util import (
    create_access_token,
    create_jwt,
    get_user_and_payload_from_jwt,
)
from cicada.api.main import app
from test.api.endpoints.common import TestEndpointWrapper
from test.common import build


class TestJwtLogic(TestEndpointWrapper):
    @classmethod
    def setup_class(cls) -> None:
        cls.app = app

        super().setup_class()

    def test_jwt_creation_logic(self) -> None:
        with self.inject_dummy_env_vars() as vars:
            user = build(User, username="admin", is_admin=True)

            jwt = create_jwt(
                subject=user.username, issuer="me", data={"hello": "world"}
            )

            user_repo = MagicMock()
            user_repo.get_user_by_username.return_value = user

            data = get_user_and_payload_from_jwt(user_repo, jwt)
            assert data

            new_user, payload = data

            user_repo.get_user_by_username.assert_called_once()

            assert new_user == user
            assert payload["iss"] == "me"
            assert payload["sub"] == "admin"
            assert payload["aud"] == vars["CICADA_DOMAIN"]

            now = int(UtcDatetime.now().timestamp())
            expiration_timeout = int(vars["JWT_TOKEN_EXPIRE_SECONDS"])

            assert payload["iat"] >= now
            assert payload["exp"] == payload["iat"] + expiration_timeout

    def test_create_jwt_from_github_sso(self) -> None:
        """
        Because GitHub is the one handling all of the auth logic, we need to
        create a new user on the fly. This means that there cannot be a hash,
        since the user's password never touches our system.

        Something that might be an issue later on is what happens when a user
        is deactivated/removed/renamed on GitHub, and a new user takes over
        that account.
        """

        with self.inject_dummy_env_vars() as vars:
            jwt = create_jwt(subject="github_user", issuer="github")

            github_user = build(
                User,
                username="github_user",
                provider="github",
            )

            user_repo = MagicMock()
            user_repo.get_user_by_username.return_value = github_user

            data = get_user_and_payload_from_jwt(user_repo, jwt)
            assert data

            new_user, payload = data

            assert new_user.username == "github_user"
            assert not new_user.password_hash
            assert not new_user.is_admin
            assert new_user.provider == "github"

            assert payload["iss"] == "github"
            assert payload["sub"] == "github_user"
            assert payload["aud"] == vars["CICADA_DOMAIN"]

            now = int(UtcDatetime.now().timestamp())
            expiration_timeout = int(vars["JWT_TOKEN_EXPIRE_SECONDS"])

            assert payload["iat"] >= now
            assert payload["exp"] == payload["iat"] + expiration_timeout

    def test_deny_access_to_endpoint_if_jwt_is_not_set(self) -> None:
        # This is testing without the JWT being set at all, which means that
        # FastAPI will catch it first, so we check here to ensure that is what
        # is actually happening.

        with self.inject_dummy_env_vars():
            response = self.client.get("/api/ping")

            assert response.status_code == 401
            assert response.json() == {"detail": "Not authenticated"}

    def test_deny_access_to_endpoint_if_jwt_is_invalid(self) -> None:
        with self.inject_dummy_env_vars():
            # TODO: move this user/jwt token creation into wrapper
            user = build(User, username="non_existent_user")

            jwt = create_access_token(user)["access_token"]

            response = self.client.get(
                "/api/ping",
                headers={"Authorization": f"Bearer {jwt}"},
            )

            assert response.status_code == 401
            assert "JWT Invalid" in response.text

    def test_allow_access_to_endpoint_if_jwt_is_valid(self) -> None:
        with self.inject_dummy_env_vars():
            user = build(User, username="admin", is_admin=True)

            jwt = create_access_token(user)["access_token"]

            response = self.client.get(
                "/api/ping",
                headers={"Authorization": f"Bearer {jwt}"},
            )

            assert response.status_code == 200
            assert "pong" in response.text

    def test_jwt_with_incorrect_audience_is_rejected(self) -> None:
        # The JWT decoder used will automatically check the audience for you,
        # this check just ensures that this happens. The audience is important
        # because the admin of one instance should not work on another
        # instance. This should be very unlikely, and would require that 2
        # services share the same password/JWT secret, but regardless this
        # should be added for added security.

        with self.inject_dummy_env_vars():
            jwt = create_jwt(
                subject="admin",
                issuer="me",
                audience="whatever",
                data={"hello": "world"},
            )

            response = self.client.get(
                "/api/ping",
                headers={"Authorization": f"Bearer {jwt}"},
            )

            assert response.status_code == 401

            # TODO: give specificy reason why JWT was rejected?
            assert "JWT Invalid" in response.text
