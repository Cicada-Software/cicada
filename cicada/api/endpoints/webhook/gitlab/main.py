import logging
from functools import partial
from typing import Any
from uuid import UUID

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
from cicada.api.settings import GitProviderSettings
from cicada.application.session.make_session_from_trigger import MakeSessionFromTrigger

from .converters import gitlab_event_to_commit, gitlab_event_to_issue

router = APIRouter()


TASK_QUEUE = TaskQueue()

logger = logging.getLogger("cicada")


def verify_webhook_came_from_gitlab(di: Di, request: Request) -> None:
    try:
        webhook_id = UUID(request.query_params.get("id"))

    except TypeError:
        raise HTTPException(400, "Workflow id is either missing or malformed") from None

    secret = request.headers.get("x-gitlab-token", "")

    webhook = di.gitlab_webhook_repo().get_webhook_by_id(webhook_id)

    if not webhook or not webhook.is_valid_secret(secret):
        raise HTTPException(
            status_code=401,
            detail="Webhook did not come from Gitlab",
        )


def handle_gitlab_push_event(  # type: ignore[misc]
    di: DiContainer, event: dict[str, Any], access_token: str
) -> None:
    cmd = MakeSessionFromTrigger(
        di.session_repo(),
        di.terminal_session_repo(),
        partial(run_workflow, access_token=access_token),
        gather_workflows=partial(gather_workflows, access_token=access_token),
        env_repo=di.environment_repo(),
        repository_repo=di.repository_repo(),
        installation_repo=di.installation_repo(),
        secret_repo=di.secret_repo(),
    )

    commit = gitlab_event_to_commit(event)

    TASK_QUEUE.add(cmd.handle(commit))


def handle_gitlab_issue_event(  # type: ignore[misc]
    di: DiContainer, event: dict[str, Any], access_token: str
) -> None:
    cmd = MakeSessionFromTrigger(
        di.session_repo(),
        di.terminal_session_repo(),
        partial(run_workflow, access_token=access_token),
        gather_workflows=partial(gather_issue_workflows, access_token=access_token),
        env_repo=di.environment_repo(),
        repository_repo=di.repository_repo(),
        installation_repo=di.installation_repo(),
        secret_repo=di.secret_repo(),
    )

    issue = gitlab_event_to_issue(event)

    TASK_QUEUE.add(cmd.handle(issue))


@router.post("/api/gitlab_webhook")
async def handle_github_event(request: Request, di: Di) -> None:
    verify_webhook_came_from_gitlab(di, request)

    webhook_id = UUID(request.query_params["id"])

    event = await request.json()

    logger.debug("Gitlab webhook data: %s", event)

    white_list = GitProviderSettings().repo_white_list

    match event:
        case {"project": {"path_with_namespace": str(repo)}}:
            if not is_repo_in_white_list(repo, white_list):
                logger.warning('Gitlab repo "%s" not in whitelist', repo)
                return

        case _:
            return

    if event["object_kind"] in {"push", "issue"}:
        update_gitlab_repo_perms(di, event)

        access_token = await get_access_token_for_webhook(di, webhook_id)

        if not access_token:
            logger.error("Could not get an access token for webhook %s", webhook_id)

            return

        if event["object_kind"] == "push":
            handle_gitlab_push_event(di, event, access_token)

        elif event["object_kind"] == "issue":
            if set(event["changes"]) & {"created_at", "closed_at"}:
                handle_gitlab_issue_event(di, event, access_token)


async def get_access_token_for_webhook(di: DiContainer, webhook_id: UUID) -> str | None:
    """
    Get an access token for a webhook. To be able to clone the repository we need to have some sort
    of token. Currently we are using the OAuth token attached to the user who created the webhook
    that is firing the event, though this might change in the future.
    """

    webhook = di.gitlab_webhook_repo().get_webhook_by_id(webhook_id)

    if not webhook:
        return None

    webhook_owner = di.user_repo().get_user_by_id(webhook.created_by_user_id)

    if not webhook_owner:
        return None

    token = await di.gitlab_token_store().load_token(webhook_owner)

    return token.access_token if token else None
