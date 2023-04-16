from importlib import reload

from fastapi.testclient import TestClient

from cicada.api import main as api_entry
from test.api.endpoints.common import TestEndpointWrapper


class TestEndabledProviders(TestEndpointWrapper):
    """
    Test that the API endpoints for github/gitlab are only loaded if they are
    in the ENABLED_PROVIDERS env var. Because the if statements that dictate
    whether the functions get added or not are defined at the top level, we
    need to do some hackery to reload the module and refresh the env vars. A
    better approach would be to use a `make_app()` function which would hide
    all the complexity of this.
    """

    @classmethod
    def setup_class(cls) -> None:
        pass

    def test_enabling_github_enables_just_github_endpoints(self) -> None:
        with self.inject_dummy_env_vars() as env_vars:
            env_vars["ENABLED_PROVIDERS"] = "github"

            reload(api_entry)
            app = api_entry.app

            client = TestClient(app)

            response = client.post("/api/github_webhook")

            assert response.status_code != 404

            response = client.post("/api/gitlab_webhook")

            assert response.status_code == 404

    def test_enabling_gitlab_enables_just_gitlab_endpoints(self) -> None:
        with self.inject_dummy_env_vars() as env_vars:
            env_vars["ENABLED_PROVIDERS"] = "gitlab"

            reload(api_entry)
            app = api_entry.app

            client = TestClient(app)

            response = client.post("/api/gitlab_webhook")

            assert response.status_code != 404

            response = client.post("/api/github_webhook")

            assert response.status_code == 404
