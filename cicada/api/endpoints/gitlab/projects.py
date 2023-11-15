import logging
from dataclasses import dataclass, field
from hashlib import sha3_256
from secrets import token_hex
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from gitlab import Gitlab, GitlabHttpError

from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser
from cicada.api.infra.gitlab.common import (
    GitlabProject,
    get_authenticated_user_id,
    get_projects_for_user,
)
from cicada.api.settings import GitlabSettings
from cicada.domain.installation import Installation, InstallationScope
from cicada.domain.repo.gitlab_webhook_repo import GitlabWebhook
from cicada.domain.user import User

router = APIRouter()


@router.get("/api/gitlab/projects")
async def get_gitlab_projects_for_user(di: Di, user: CurrentUser) -> list[GitlabProject]:
    token = await di.gitlab_token_store().load_token(user)

    if not token:
        raise HTTPException(401)

    gl = Gitlab(oauth_token=token.access_token)

    user_id = get_authenticated_user_id(gl)

    # TODO: add flag to show if hook already exists for project
    return get_projects_for_user(gl, user_id)


@dataclass
class UpdateProjectWebhooks:
    all: bool = False
    project_ids: list[int] = field(default_factory=list)


@router.post("/api/gitlab/projects/add_webhooks")
async def add_webhooks_to_projects(di: Di, user: CurrentUser, cmd: UpdateProjectWebhooks) -> None:
    token = await di.gitlab_token_store().load_token(user)

    if not token:
        raise HTTPException(401)

    gl = Gitlab(oauth_token=token.access_token)
    user_id = get_authenticated_user_id(gl)

    if cmd.all:
        project_ids = [p.id for p in get_projects_for_user(gl, user_id)]

    else:
        project_ids = cmd.project_ids

    for project_id in project_ids:
        try:
            update_webhook_for_project(di, gl, user, project_id)

        except GitlabHttpError:
            logger = logging.getLogger("cicada")
            logger.exception("Gitlab API call failed")

            continue


def update_webhook_for_project(di: Di, gl: Gitlab, user: User, project_id: int) -> None:
    settings = GitlabSettings()

    # TODO: make this lazy again
    project = gl.projects.get(project_id)
    hooks = project.hooks.list()

    url = f"https://{settings.domain}/api/gitlab_webhook"

    if url in [hook.url.split("?")[0] for hook in hooks]:
        # Webhook with our domain already exists, ignore
        return

    secret = token_hex(16)
    webhook_id = uuid4()

    hook = project.hooks.create(
        {
            "id": project_id,
            "url": f"https://{settings.domain}/api/gitlab_webhook?id={webhook_id}",
            "enable_ssl_verification": True,
            "issues_events": True,
            "push_events": True,
            "token": secret,
        }
    )

    webhook = GitlabWebhook(
        id=webhook_id,
        created_by_user_id=user.id,
        project_id=project_id,
        hook_id=hook.id,
        hashed_secret=sha3_256(secret.encode()).hexdigest(),
    )
    di.gitlab_webhook_repo().add_webhook(webhook)

    hook_url = f"https://gitlab.com/{user.username}/{project.path}/-/hooks/{hook.id}/edit"

    installation = Installation(
        id=uuid4(),
        name=user.username,
        provider="gitlab",
        scope=InstallationScope.USER,
        admin_id=user.id,
        provider_id=str(hook.id),
        provider_url=hook_url,
    )

    di.installation_repo().create_or_update_installation(installation)
