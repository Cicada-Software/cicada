# ruff: noqa: E501

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from cicada.api.domain.session import Session, SessionStatus
from cicada.api.domain.terminal_session import TerminalSession
from cicada.api.endpoints.webhook.gitlab.converters import (
    gitlab_event_to_commit,
    gitlab_event_to_issue,
)
from cicada.api.endpoints.webhook.gitlab.main import TASK_QUEUE
from cicada.api.endpoints.webhook.gitlab.main import router as gitlab_webhook
from test.api.endpoints.common import TestEndpointWrapper


class TestGitlabWebhook(TestEndpointWrapper):
    @classmethod
    def setup_class(cls) -> None:
        super().setup_class()

        cls.app.include_router(gitlab_webhook)

    def test_incorrect_or_unset_token_secret_is_rejected(self) -> None:
        with self.inject_dummy_env_vars():
            response = self.client.post("/api/gitlab_webhook", json={})

            assert response.status_code == 401
            assert "Webhook did not come from Gitlab" in response.text

    def test_create_issue_webhook(self) -> None:
        json_file = Path("test/api/infra/gitlab/test_data/issue_open.json")
        event = json.loads(json_file.read_text())

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        # ensure that we (for whatever reason) arent using dev data
        assert not sessions

        with (
            self.inject_dummy_env_vars() as vars,
            self.mock_gitlab_infra_details() as mocks,
        ):

            async def f(session: Session, _: TerminalSession) -> None:
                session.finish(SessionStatus.SUCCESS)

            mocks["run_workflow"].side_effect = f
            mocks["repo_get_env"].return_value = {}

            # could be anything, will fail once value is actually used
            mocks["gather_issue_workflows"].return_value = [1]

            response = self.client.post(
                "/api/gitlab_webhook",
                json=event,
                headers={"x-gitlab-token": vars["GITLAB_WEBHOOK_SECRET"]},
            )

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert len(sessions) == 1

        session = sessions[0]
        assert session.status == SessionStatus.SUCCESS
        assert session.finished_at
        assert session.trigger == gitlab_event_to_issue(event)

        assert not TASK_QUEUE

    def test_git_push_webhook(self) -> None:
        self.di.reset()

        json_file = Path("test/api/infra/gitlab/test_data/git_push.json")
        event = json.loads(json_file.read_text())

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

        with (
            self.inject_dummy_env_vars() as vars,
            self.mock_gitlab_infra_details() as mocks,
        ):

            async def f(session: Session, _: TerminalSession) -> None:
                session.finish(SessionStatus.SUCCESS)

            mocks["run_workflow"].side_effect = f
            mocks["repo_get_env"].return_value = {}

            # could be anything, will fail once value is actually used
            mocks["gather_workflows"].return_value = [1]

            response = self.client.post(
                "/api/gitlab_webhook",
                json=event,
                headers={"x-gitlab-token": vars["GITLAB_WEBHOOK_SECRET"]},
            )

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert len(sessions) == 1

        session = sessions[0]
        assert session.status == SessionStatus.SUCCESS
        assert session.finished_at
        assert session.trigger == gitlab_event_to_commit(event)

        assert not TASK_QUEUE

    def test_event_from_repository_not_in_white_list_is_ignored(self) -> None:
        self.di.reset()

        json_file = Path("test/api/infra/gitlab/test_data/git_push.json")
        event = json.loads(json_file.read_text())

        # Fullname could be anything, just so long as it doesnt match any of
        # the regexs in the repo white list.
        event["project"]["path_with_namespace"] = "unknown_user/unknown_repo"

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

        with (
            self.mock_gitlab_infra_details(),
            self.inject_dummy_env_vars() as vars,
        ):
            response = self.client.post(
                "/api/gitlab_webhook",
                json=event,
                headers={"x-gitlab-token": vars["GITLAB_WEBHOOK_SECRET"]},
            )

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

    def test_event_which_doesnt_include_repository_is_ignored(self) -> None:
        self.di.reset()

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

        with (
            self.mock_gitlab_infra_details(),
            self.inject_dummy_env_vars() as vars,
        ):
            response = self.client.post(
                "/api/gitlab_webhook",
                json={},
                headers={"x-gitlab-token": vars["GITLAB_WEBHOOK_SECRET"]},
            )

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

    @contextmanager
    def mock_gitlab_infra_details(self) -> Iterator[dict[str, Mock]]:
        # fmt: off

        pkg = "cicada.api.endpoints.webhook.gitlab.main"
        pkg2 = "cicada.api.domain.services.repository"

        with (
            patch(f"{pkg}.run_workflow") as run_workflow,
            patch(f"{pkg}.gather_workflows") as gather_workflows,
            patch(f"{pkg}.gather_issue_workflows") as gather_issue_workflows,
            patch(f"{pkg2}.get_env_vars_for_repo") as get_env,
        ):
            yield {
                "run_workflow": run_workflow,
                "gather_workflows": gather_workflows,
                "gather_issue_workflows": gather_issue_workflows,
                "repo_get_env": get_env,
            }
