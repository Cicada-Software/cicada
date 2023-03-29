from uuid import uuid4

from cicada.api.main import app
from test.api.endpoints.common import TestEndpointWrapper


class TestMainEndpoints(TestEndpointWrapper):
    @classmethod
    def setup_class(cls) -> None:
        cls.app = app

        super().setup_class()

    def test_html_pages_return_html_content(self) -> None:
        urls = ("/runs", f"/run/{uuid4()}", "/dashboard", "/")

        for url in urls:
            response = self.client.get(url)

            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html;")
            assert "<!DOCTYPE html>" in response.text

    def test_run_page_must_be_a_uuid(self) -> None:
        response = self.client.get("/run/not-a-uuid")

        assert response.status_code == 422

    def test_no_unauthorized_access_to_api_endpoints(self) -> None:
        urls = ("/session/recent", f"session/{uuid4()}/session_info", "/ping")

        for url in urls:
            response = self.client.get(url)

            assert response.status_code == 401

    def test_invalid_email_on_waitlist_page_returns_400_error(self) -> None:
        response = self.client.post(
            "/join_waitlist", data={"email": "invalid"}
        )

        assert response.status_code == 400

        assert "Email must contain" in response.text

    def test_valid_email_inserts_into_waitlist(self) -> None:
        response = self.client.post(
            "/join_waitlist", data={"email": "valid@email.com"}
        )

        assert response.status_code == 200

        emails = self.di.waitlist_repo().get_emails()

        assert len(emails) == 1
        assert emails[0][1] == "valid@email.com"
