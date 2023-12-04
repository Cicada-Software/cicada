# ruff: noqa: E501

import json
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha3_256
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from cicada.api.endpoints.webhook.gitlab.converters import (
    gitlab_event_to_commit,
    gitlab_event_to_issue,
)
from cicada.api.endpoints.webhook.gitlab.main import TASK_QUEUE
from cicada.api.endpoints.webhook.gitlab.main import router as gitlab_webhook
from cicada.ast.nodes import FileNode
from cicada.domain.repo.gitlab_webhook_repo import GitlabWebhook
from cicada.domain.session import SessionStatus, Workflow, WorkflowStatus
from cicada.domain.triggers import GitSha, Trigger
from cicada.domain.user import User
from test.api.endpoints.common import TestEndpointWrapper
from test.common import build


async def dummy_gather(trigger: Trigger, repo: Path, **_) -> list[FileNode]:  # type: ignore
    if not trigger.sha:
        trigger.sha = GitSha("deadbeef")

    return [FileNode([], file=repo / "file.ci")]


class TestGitlabWebhook(TestEndpointWrapper):
    @classmethod
    def setup_class(cls) -> None:
        super().setup_class()

        cls.app.include_router(gitlab_webhook)

    def test_create_issue_webhook(self) -> None:
        json_file = Path("test/api/infra/gitlab/test_data/issue_open.json")
        event = json.loads(json_file.read_text())

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        # ensure that we (for whatever reason) arent using dev data
        assert not sessions

        with (
            self.inject_dummy_env_vars(),
            self.mock_gitlab_infra_details() as mocks,
            self.disable_webhook_verification(),
        ):

            async def run(*args, **__) -> None:  # type: ignore
                workflow: Workflow = args[-1]
                workflow.finish(WorkflowStatus.SUCCESS)

            mocks["run_workflow"].side_effect = run
            mocks["repo_get_env"].return_value = {}

            mocks["gather_issue_workflows"].side_effect = dummy_gather

            response = self.client.post(f"/api/gitlab_webhook?id={uuid4()}", json=event)

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert len(sessions) == 1

        session = sessions[0]
        assert session.status == SessionStatus.SUCCESS
        assert session.finished_at

        assert session.trigger.sha == GitSha("deadbeef")

        session.trigger.sha = None

        assert session.trigger == gitlab_event_to_issue(event)

        assert not TASK_QUEUE

    def test_git_push_webhook(self) -> None:
        self.di.reset()

        json_file = Path("test/api/infra/gitlab/test_data/git_push.json")
        event = json.loads(json_file.read_text())

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

        with (
            self.inject_dummy_env_vars(),
            self.mock_gitlab_infra_details() as mocks,
            self.disable_webhook_verification(),
        ):

            async def run(*args, **__) -> None:  # type: ignore
                workflow: Workflow = args[-1]
                workflow.finish(WorkflowStatus.SUCCESS)

            mocks["run_workflow"].side_effect = run
            mocks["repo_get_env"].return_value = {}

            mocks["gather_workflows"].side_effect = dummy_gather

            response = self.client.post(f"/api/gitlab_webhook?id={uuid4()}", json=event)

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
            self.inject_dummy_env_vars(),
            self.disable_webhook_verification(),
        ):
            response = self.client.post(f"/api/gitlab_webhook?id={uuid4()}", json=event)

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

    def test_event_which_doesnt_include_repository_is_ignored(self) -> None:
        self.di.reset()

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

        with (
            self.mock_gitlab_infra_details(),
            self.inject_dummy_env_vars(),
            self.disable_webhook_verification(),
        ):
            response = self.client.post(f"/api/gitlab_webhook?id={uuid4()}", json={})

            assert response.status_code == 200

        sessions = self.di.session_repo().get_recent_sessions_as_admin()

        assert not sessions

    def test_missing_workflow_id_raises_error(self) -> None:
        self.di.reset()

        with (
            self.mock_gitlab_infra_details(),
            self.inject_dummy_env_vars(),
        ):
            response = self.client.post(
                "/api/gitlab_webhook",
                json={},
                headers={"x-gitlab-token": "anything"},
            )

            assert response.status_code == 400
            assert "Workflow id is either missing or malformed" in response.text

    def test_nonexistent_webhook_id_causes_failure(self) -> None:
        self.di.reset()

        with (
            self.mock_gitlab_infra_details(),
            self.inject_dummy_env_vars(),
        ):
            response = self.client.post(
                f"/api/gitlab_webhook?id={uuid4()}",
                json={},
                headers={"x-gitlab-token": "anything"},
            )

            assert response.status_code == 401
            assert "Webhook did not come from Gitlab" in response.text

    def test_verification_fails_if_hash_doesnt_match(self) -> None:
        self.di.reset()

        webhook_repo = self.di.gitlab_webhook_repo()
        user_repo = self.di.user_repo()

        user = build(User)
        user_repo.create_or_update_user(user)

        webhook = GitlabWebhook(
            id=uuid4(),
            created_by_user_id=user.id,
            project_id=123,
            hook_id=456,
            hashed_secret="wont match this",  # noqa: S106
        )
        webhook_repo.add_webhook(webhook)

        with (
            self.mock_gitlab_infra_details(),
            self.inject_dummy_env_vars(),
        ):
            response = self.client.post(
                f"/api/gitlab_webhook?id={webhook.id}",
                json={},
                headers={"x-gitlab-token": "hash wont match"},
            )

            assert response.status_code == 401
            assert "Webhook did not come from Gitlab" in response.text

    def test_verification_passes_if_workflow_id_and_secret_are_valid(self) -> None:
        self.di.reset()

        webhook_repo = self.di.gitlab_webhook_repo()
        user_repo = self.di.user_repo()

        user = build(User)
        user_repo.create_or_update_user(user)

        secret = "testing webhook secret"  # noqa: S105

        webhook = GitlabWebhook(
            id=uuid4(),
            created_by_user_id=user.id,
            project_id=123,
            hook_id=456,
            hashed_secret=sha3_256(secret.encode()).hexdigest(),
        )
        webhook_repo.add_webhook(webhook)

        with (
            self.mock_gitlab_infra_details(),
            self.inject_dummy_env_vars(),
        ):
            response = self.client.post(
                f"/api/gitlab_webhook?id={webhook.id}",
                json={},
                headers={"x-gitlab-token": secret},
            )

            assert response.status_code == 200

    @staticmethod
    @contextmanager
    def mock_gitlab_infra_details() -> Iterator[dict[str, Mock]]:
        # fmt: off

        pkg = "cicada.api.endpoints.webhook.gitlab.main"
        pkg2 = "cicada.domain.services.repository"

        with (
            patch(f"{pkg}.run_workflow") as run_workflow,
            patch(f"{pkg}.gather_workflows") as gather_workflows,
            patch(f"{pkg}.gather_issue_workflows") as gather_issue_workflows,
            patch(f"{pkg2}.get_env_vars_for_repo") as get_env,
            patch(f"{pkg}.get_access_token_for_webhook"),
        ):
            yield {
                "run_workflow": run_workflow,
                "gather_workflows": gather_workflows,
                "gather_issue_workflows": gather_issue_workflows,
                "repo_get_env": get_env,
            }

    @staticmethod
    @contextmanager
    def disable_webhook_verification() -> Iterator[Mock]:
        pkg = "cicada.api.endpoints.webhook.gitlab.main"

        with patch(f"{pkg}.verify_webhook_came_from_gitlab") as m:
            yield m
