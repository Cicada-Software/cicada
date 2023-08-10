# ruff: noqa: E501

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from cicada.api.endpoints.webhook.github.converters import (
    github_event_to_commit,
    github_event_to_issue,
)
from cicada.api.endpoints.webhook.github.main import TASK_QUEUE
from cicada.api.endpoints.webhook.github.main import router as github_webhook
from cicada.domain.session import Session, SessionStatus
from test.api.endpoints.common import TestEndpointWrapper


class TestGitHubWebhooks(TestEndpointWrapper):
    @classmethod
    def setup_class(cls) -> None:
        super().setup_class()

        cls.app.include_router(github_webhook)

    def test_unsigned_webhook_is_rejected(self) -> None:
        with self.inject_dummy_env_vars():
            response = self.client.post("/api/github_webhook", json={})

            assert response.status_code == 401
            assert "not signed" in response.text

    def test_session_is_created_from_issue_open_trigger(self) -> None:
        json_file = Path(
            "test/api/infra/github/test_data/issue_open_event.json"
        )
        event = json.loads(json_file.read_text())

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        # ensure that we (for whatever reason) arent using dev data
        assert not sessions

        with (
            self.disable_github_signing_verification(),
            self.mock_github_infra_details() as mocks,
        ):
            mocks["repo_get_env"].return_value = {}

            async def f(session: Session, *_, **__) -> None:  # type: ignore
                session.finish(SessionStatus.SUCCESS)

            mocks["run_workflow"].side_effect = f
            mocks["gather_issues"].return_value = [1]

            response = self.client.post(
                "/api/github_webhook",
                json=event,
                headers={"x-github-event": "issues"},
            )

            assert response.status_code == 200

            sessions = self.di.session_repo().get_recent_sessions_as_admin()

            assert len(sessions) == 1

            session = sessions[0]
            assert session.status == SessionStatus.SUCCESS
            assert session.finished_at
            assert session.trigger == github_event_to_issue(event)

            assert not TASK_QUEUE

    # TODO: dedupe
    def test_session_is_created_from_git_push_trigger(self) -> None:
        # TODO: allow for resetting without rerunning migration
        self.di.reset()

        json_file = Path("test/api/infra/github/test_data/push_event.json")
        event = json.loads(json_file.read_text())

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

        with (
            self.disable_github_signing_verification(),
            self.mock_github_infra_details() as mocks,
        ):
            mocks["repo_get_env"].return_value = {}

            async def f(session: Session, *_, **__) -> None:  # type: ignore
                session.finish(SessionStatus.SUCCESS)

            mocks["run_workflow"].side_effect = f
            mocks["gather_git_pushes"].return_value = [1]

            response = self.client.post(
                "/api/github_webhook",
                json=event,
                headers={"x-github-event": "push"},
            )

            assert response.status_code == 200

            sessions = self.di.session_repo().get_recent_sessions_as_admin()

            assert len(sessions) == 1

            session = sessions[0]
            assert session.status == SessionStatus.SUCCESS
            assert session.finished_at
            assert session.trigger == github_event_to_commit(event)

            assert not TASK_QUEUE

    def test_event_from_repository_not_in_white_list_is_ignored(self) -> None:
        self.di.reset()

        json_file = Path("test/api/infra/github/test_data/push_event.json")
        event = json.loads(json_file.read_text())

        # Fullname could be anything, just so long as it doesnt match any of
        # the regexs in the repo white list.
        event["repository"]["full_name"] = "unknown_user/unknown_repo"

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

        with (
            self.disable_github_signing_verification(),
            self.mock_github_infra_details(),
        ):
            response = self.client.post(
                "/api/github_webhook",
                json=event,
                headers={"x-github-event": "push"},
            )

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

    def test_event_which_doesnt_include_repository_is_ignored(self) -> None:
        self.di.reset()

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

        with (
            self.disable_github_signing_verification(),
            self.mock_github_infra_details(),
        ):
            response = self.client.post(
                "/api/github_webhook",
                json={},
                headers={"x-github-event": "push"},
            )

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

    @contextmanager
    def disable_github_signing_verification(self) -> Iterator[None]:
        with patch(
            "cicada.api.endpoints.webhook.github.main.verify_webhook_is_signed_by_github",
            return_value=None,
        ):
            yield

    @contextmanager
    def mock_github_infra_details(self) -> Iterator[dict[str, Mock]]:
        # fmt: off

        pkg = "cicada.api.endpoints.webhook.github.main"
        pkg2 = "cicada.domain.services.repository"

        with (
            patch(f"{pkg}.update_github_repo_perms"),
            patch(f"{pkg}.create_or_update_github_installation"),
            patch(f"{pkg}.create_or_update_github_user"),
            patch(f"{pkg}.run_workflow") as run_workflow,
            patch(f"{pkg}.gather_issue_workflows", return_value=True) as gather_issues,
            patch(f"{pkg}.gather_workflows_via_trigger", return_value=True) as gather_git_pushes,
            patch(f"{pkg}.send_email") as send_email,
            patch(f"{pkg2}.get_env_vars_for_repo") as get_env,

        ):
            yield {
                "run_workflow": run_workflow,
                "gather_issues": gather_issues,
                "gather_git_pushes": gather_git_pushes,
                "repo_get_env": get_env,
                "send_email": send_email,
            }
