from cicada.api.common.datetime import UtcDatetime
from cicada.api.endpoints.login import router as login_router
from cicada.api.endpoints.login_util import get_user_and_payload_from_jwt
from test.api.endpoints.common import TestEndpointWrapper


class TestLoginEndpoints(TestEndpointWrapper):
    @classmethod
    def setup_class(cls) -> None:
        super().setup_class()

        cls.app.include_router(login_router)

    def test_login_and_refresh_token_works(self) -> None:
        response = self.client.post(
            "/login",
            data={"username": "admin", "password": self.test_admin_pw},
        )

        assert response.status_code == 200

        jwt = response.json()["access_token"]

        data = get_user_and_payload_from_jwt(self.di.user_repo(), jwt)
        assert data

        user, payload = data

        assert user.username == "admin"
        assert not user.password_hash
        assert user.is_admin
        assert user.provider == "cicada"

        assert payload["exp"] > UtcDatetime.now().timestamp()
        assert payload["sub"] == "admin"
        assert payload["iss"] == "cicada"

        # refresh token logic tests

        response = self.client.post(
            "/refresh_token",
            headers={"Authorization": f"bearer {jwt}"},
        )

        refresh_jwt = response.json()["access_token"]

        refresh_data = get_user_and_payload_from_jwt(
            self.di.user_repo(), refresh_jwt
        )
        assert refresh_data

        refresh_user, refresh_payload = refresh_data

        assert refresh_user == user

        assert refresh_payload["exp"] >= payload["exp"]
        assert refresh_payload["sub"] == payload["sub"]
        assert refresh_payload["iss"] == payload["iss"]

    def test_non_existent_user_login_returns_unauthorized(self) -> None:
        response = self.client.post(
            "/login",
            data={"username": "invalid", "password": "password"},
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.text

    def test_invalid_jwt_is_not_allowed(self) -> None:
        response = self.client.post(
            "/refresh_token",
            headers={"Authorization": "bearer invalid"},
        )

        assert response.status_code == 401
        assert "JWT Invalid" in response.text
