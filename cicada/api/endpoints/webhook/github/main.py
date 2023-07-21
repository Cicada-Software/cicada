import hashlib
import hmac
import logging
from asyncio import Task, create_task
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from cicada.api.di import DiContainer
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.webhook.common import is_repo_in_white_list
from cicada.api.infra.github.auth import (
    add_repository_to_installation,
    create_or_update_github_installation,
    create_or_update_github_user,
    update_github_repo_perms,
)
from cicada.api.infra.github.common import gather_workflows_via_trigger
from cicada.api.infra.github.workflows import (
    gather_issue_workflows,
    run_workflow,
)
from cicada.api.settings import GitHubSettings, GitProviderSettings
from cicada.application.session.make_session_from_trigger import (
    MakeSessionFromTrigger,
)

from .converters import github_event_to_commit, github_event_to_issue

router = APIRouter()

TASK_QUEUE: set[Task[None]] = set()


logger = logging.getLogger("cicada")


def handle_github_push_event(  # type: ignore[misc]
    di: DiContainer, event: dict[str, Any]
) -> None:
    cmd = MakeSessionFromTrigger(
        di.session_repo(),
        di.terminal_session_repo(),
        gather_workflows=gather_workflows_via_trigger,
        workflow_runner=run_workflow,
        env_repo=di.environment_repo(),
        repository_repo=di.repository_repo(),
    )

    commit = github_event_to_commit(event)
    result = cmd.handle(commit)

    task = create_task(result)
    TASK_QUEUE.add(task)
    task.add_done_callback(TASK_QUEUE.discard)


def handle_github_issue_event(  # type: ignore[misc]
    di: DiContainer, event: dict[str, Any]
) -> None:
    cmd = MakeSessionFromTrigger(
        di.session_repo(),
        di.terminal_session_repo(),
        gather_workflows=gather_issue_workflows,
        workflow_runner=run_workflow,
        env_repo=di.environment_repo(),
        repository_repo=di.repository_repo(),
    )

    issue = github_event_to_issue(event)
    result = cmd.handle(issue)

    task = create_task(result)
    TASK_QUEUE.add(task)
    task.add_done_callback(TASK_QUEUE.discard)


async def verify_webhook_is_signed_by_github(request: Request) -> None:
    expected_digest = hmac.new(
        GitHubSettings().webhook_secret.encode(),
        await request.body(),
        hashlib.sha256,
    ).hexdigest()

    with suppress(Exception):
        digest = request.headers.get("x-hub-signature-256", "").split("=")[1]
        if digest == expected_digest:  # pragma: no cover
            return

    logger.warning("GitHub webhook was not signed by GitHub!")

    raise HTTPException(status_code=401, detail="HMAC is not signed by GitHub")


@router.post("/api/github_webhook")
async def handle_github_event(request: Request, di: Di) -> None:
    await verify_webhook_is_signed_by_github(request)

    event_type = request.headers["x-github-event"]

    event = await request.json()

    logger.debug(f"GitHub event type: {event_type}")
    logger.debug(f"GitHub webhook data: {event}")

    white_list = GitProviderSettings().repo_white_list

    match event:
        case {"repository": {"full_name": str(repo_name)}}:
            if not is_repo_in_white_list(repo_name, white_list):
                logger.warning(f'GitHub repo "{repo_name}" not in whitelist')
                return

        case _:
            return

    user = create_or_update_github_user(di.user_repo(), event)

    if user:
        repo = update_github_repo_perms(di, user.id, event, event_type)

        # TODO: update this without the need to have a repo/user
        if repo:
            add_repository_to_installation(di.installation_repo(), repo, event)

    if event_type in ("installation", "installation_repositories"):
        if user:
            create_or_update_github_installation(di, user.id, event)

    elif event_type == "push":
        if event["deleted"] is not True:
            handle_github_push_event(di, event)

    elif event_type == "issues":
        if event["action"] in ("opened", "closed"):
            handle_github_issue_event(di, event)
