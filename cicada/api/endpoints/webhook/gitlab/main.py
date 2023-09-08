import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from cicada.api.di import DiContainer
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.task_queue import TaskQueue
from cicada.api.endpoints.webhook.common import is_repo_in_white_list
from cicada.api.infra.gitlab.auth import update_gitlab_repo_perms
from cicada.api.infra.gitlab.workflows import (
    gather_issue_workflows,
    gather_workflows,
    run_workflow,
)
from cicada.api.settings import GitlabSettings, GitProviderSettings
from cicada.application.session.make_session_from_trigger import (
    MakeSessionFromTrigger,
)

from .converters import gitlab_event_to_commit, gitlab_event_to_issue

router = APIRouter()


TASK_QUEUE = TaskQueue()

logger = logging.getLogger("cicada")


def verify_webhook_came_from_gitlab(request: Request) -> None:
    secret = request.headers.get("x-gitlab-token")

    if secret != GitlabSettings().webhook_secret:
        raise HTTPException(
            status_code=401,
            detail="Webhook did not come from Gitlab",
        )


def handle_gitlab_push_event(  # type: ignore[misc]
    di: DiContainer, event: dict[str, Any]
) -> None:
    cmd = MakeSessionFromTrigger(
        di.session_repo(),
        di.terminal_session_repo(),
        run_workflow,
        gather_workflows=gather_workflows,
        env_repo=di.environment_repo(),
        repository_repo=di.repository_repo(),
        installation_repo=di.installation_repo(),
        secret_repo=di.secret_repo(),
    )

    commit = gitlab_event_to_commit(event)

    TASK_QUEUE.add(cmd.handle(commit))


def handle_gitlab_issue_event(  # type: ignore[misc]
    di: DiContainer, event: dict[str, Any]
) -> None:
    cmd = MakeSessionFromTrigger(
        di.session_repo(),
        di.terminal_session_repo(),
        run_workflow,
        gather_workflows=gather_issue_workflows,
        env_repo=di.environment_repo(),
        repository_repo=di.repository_repo(),
        installation_repo=di.installation_repo(),
        secret_repo=di.secret_repo(),
    )

    issue = gitlab_event_to_issue(event)

    TASK_QUEUE.add(cmd.handle(issue))


@router.post("/api/gitlab_webhook")
async def handle_github_event(request: Request, di: Di) -> None:
    verify_webhook_came_from_gitlab(request)

    event = await request.json()

    logger.debug(f"Gitlab webhook data: {event}")

    white_list = GitProviderSettings().repo_white_list

    match event:
        case {"project": {"path_with_namespace": str(repo)}}:
            if not is_repo_in_white_list(repo, white_list):
                logger.warning(f'Gitlab repo "{repo}" not in whitelist')
                return

        case _:
            return

    if event["object_kind"] in ("push", "issue"):
        update_gitlab_repo_perms(di, event)

    if event["object_kind"] == "push":
        handle_gitlab_push_event(di, event)

    elif event["object_kind"] == "issue":
        if set(event["changes"]) & {"created_at", "closed_at"}:
            handle_gitlab_issue_event(di, event)
