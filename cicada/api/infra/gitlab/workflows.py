from collections.abc import AsyncGenerator
from contextlib import (
    AbstractAsyncContextManager,
    asynccontextmanager,
    nullcontext,
)
from pathlib import Path
from urllib.parse import urlparse

import gitlab

from cicada.api.common.http import url_get_user_and_repo
from cicada.api.common.json import asjson
from cicada.api.domain.session import Session, SessionStatus
from cicada.api.domain.terminal_session import TerminalSession
from cicada.api.domain.triggers import CommitTrigger, GitSha, Trigger
from cicada.api.infra.gitlab.common import gitlab_clone_url
from cicada.api.infra.repo_get_ci_files import repo_get_ci_files
from cicada.api.infra.run_program import (
    ExecutionContext,
    exit_code_to_status_code,
    run_docker_workflow,
)
from cicada.api.settings import GitlabSettings


@asynccontextmanager
async def wrap_in_gitlab_status_check(
    session: Session,
) -> AsyncGenerator[None, None]:  # pragma: no cover
    settings = GitlabSettings()

    # TODO: add UTC timestamp for when the checks are finished

    assert isinstance(session.trigger, CommitTrigger)

    project_id = urlparse(session.trigger.repository_url).path[1:]

    gl = gitlab.Gitlab(private_token=settings.access_token)
    project = gl.projects.get(project_id, lazy=True)
    commit = project.commits.get(str(session.trigger.sha))

    payload = {
        "sha": str(session.trigger.sha),
        "state": "running",
        "name": "Cicada",
        "target_url": f"http://{settings.domain}/run/{session.id}",
    }

    commit.statuses.create(payload)

    try:
        yield

    except Exception as ex:
        commit.statuses.create({**payload, "state": "failed"})

        raise ex

    state = "success" if session.status == SessionStatus.SUCCESS else "failed"

    commit.statuses.create({**payload, "state": state})


async def run_workflow(
    session: Session, terminal: TerminalSession, env: dict[str, str]
) -> None:
    settings = GitlabSettings()

    wrapper: AbstractAsyncContextManager[None]

    if session.trigger.type == "git.push":
        wrapper = wrap_in_gitlab_status_check(session)
    else:
        wrapper = nullcontext()

    username, repo_name = url_get_user_and_repo(session.trigger.repository_url)

    url = gitlab_clone_url(username, repo_name, settings.access_token)

    try:
        async with wrapper:
            exit_code = await run_docker_workflow(
                ExecutionContext(
                    url=url,
                    trigger_type=session.trigger.type,
                    trigger=asjson(session.trigger),
                    terminal=terminal,
                    env=env,
                )
            )

            session.finish(exit_code_to_status_code(exit_code))

    except Exception as ex:
        session.finish(SessionStatus.FAILURE)

        raise ex


async def gather_issue_workflows(trigger: Trigger) -> list[Path]:
    settings = GitlabSettings()
    user, repo = url_get_user_and_repo(trigger.repository_url)

    gl = gitlab.Gitlab(private_token=settings.access_token)

    project = gl.projects.get(f"{user}/{repo}", lazy=True)
    commit = project.commits.get("HEAD")

    trigger.sha = GitSha(str(commit.get_id()))

    return await gather_workflows(trigger)


async def gather_workflows(trigger: Trigger) -> list[Path]:
    username, repo_name = url_get_user_and_repo(trigger.repository_url)

    settings = GitlabSettings()

    url = gitlab_clone_url(username, repo_name, settings.access_token)

    assert trigger.sha

    files_or_errors = await repo_get_ci_files(url, str(trigger.sha), trigger)

    return [x for x in files_or_errors if isinstance(x, Path)]
