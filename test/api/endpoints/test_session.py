from copy import deepcopy
from uuid import uuid4

from cicada.api.common.json import asjson
from cicada.api.domain.session import Session, SessionStatus
from cicada.api.domain.user import User
from cicada.api.endpoints.login_util import create_access_token
from cicada.api.endpoints.session import router as session_router
from test.api.endpoints.common import TestEndpointWrapper
from test.common import build


class TestSessionEndpoints(TestEndpointWrapper):
    @classmethod
    def setup_class(cls) -> None:
        super().setup_class()

        cls.app.include_router(session_router)

    def test_stop_session(self) -> None:
        session = build(Session)
        self.di.session_repo().create(session)

        with self.inject_dummy_env_vars():
            user = build(User, username="admin", is_admin=True)

            jwt = create_access_token(user)["access_token"]

            response = self.client.post(
                f"/api/session/{session.id}/stop",
                headers={"Authorization": f"Bearer {jwt}"},
            )

            assert response.status_code == 200

            sessions = self.di.session_repo().get_recent_sessions_as_admin()

            assert sessions
            assert sessions[0].finished_at
            assert sessions[0].status == SessionStatus.STOPPED

    def test_get_recent_sessions(self) -> None:
        self.di.reset()

        session = build(Session)
        self.di.session_repo().create(session)

        with self.inject_dummy_env_vars():
            user = build(User, username="admin", is_admin=True)

            jwt = create_access_token(user)["access_token"]

            response = self.client.get(
                "/api/session/recent",
                headers={"Authorization": f"Bearer {jwt}"},
            )

            assert response.status_code == 200

            sessions = self.di.session_repo().get_recent_sessions_as_admin()

            assert sessions == [session]
            assert response.json() == [asjson(session)]

    def test_get_session_info(self) -> None:
        self.di.reset()

        session = build(Session)

        run_2 = deepcopy(session)
        run_2.run = 2

        self.di.session_repo().create(session)
        self.di.session_repo().create(run_2)

        with self.inject_dummy_env_vars():
            user = build(User, username="admin", is_admin=True)

            jwt = create_access_token(user)["access_token"]

            response = self.client.get(
                f"/api/session/{session.id}/session_info",
                headers={"Authorization": f"Bearer {jwt}"},
            )

            # No "run" query param defaults to most recent run, which is 2
            # in this case
            assert response.status_code == 200
            assert response.json() == asjson(run_2)

            response = self.client.get(
                f"/api/session/{session.id}/session_info?run=1",
                headers={"Authorization": f"Bearer {jwt}"},
            )

            assert response.status_code == 200
            assert response.json() == asjson(session)

    def test_session_info_returns_404_when_session_doesnt_exist(self) -> None:
        self.di.reset()

        with self.inject_dummy_env_vars():
            user = build(User, username="admin", is_admin=True)

            jwt = create_access_token(user)["access_token"]

            response = self.client.get(
                f"/api/session/{uuid4()}/session_info",
                headers={"Authorization": f"Bearer {jwt}"},
            )

            assert response.status_code == 404
            assert "Session not found" in response.text
