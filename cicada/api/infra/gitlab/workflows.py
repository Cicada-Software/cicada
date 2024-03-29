from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext
from pathlib import Path
from urllib.parse import urlparse

import gitlab

from cicada.api.di import DiContainer
from cicada.api.infra.common import url_get_user_and_repo
from cicada.api.infra.gitlab.common import gitlab_clone_url
from cicada.api.infra.repo_get_ci_files import repo_get_ci_files
from cicada.api.infra.run_program import (
    RemoteDockerLikeExecutionContext,
    exit_code_to_status_code,
    get_execution_type,
)
from cicada.api.settings import ExecutionSettings, GitlabSettings
from cicada.ast.generate import AstError
from cicada.ast.nodes import FileNode
from cicada.domain.session import Session, Workflow, WorkflowStatus
from cicada.domain.terminal_session import TerminalSession
from cicada.domain.triggers import CommitTrigger, GitSha, Trigger


@asynccontextmanager
async def wrap_in_gitlab_status_check(
    session: Session, workflow: Workflow, access_token: str
) -> AsyncGenerator[None, None]:  # pragma: no cover
    settings = GitlabSettings()

    # TODO: add UTC timestamp for when the checks are finished

    assert isinstance(session.trigger, CommitTrigger)

    namespace = urlparse(session.trigger.repository_url).path[1:]

    gl = gitlab.Gitlab(oauth_token=access_token)
    project = gl.projects.get(namespace, lazy=True)
    commit = project.commits.get(str(session.trigger.sha))

    payload = {
        "sha": str(session.trigger.sha),
        "state": "running",
        "name": workflow.title or "Cicada",
        "target_url": f"https://{settings.domain}/run/{session.id}?run={session.run}",
    }

    commit.statuses.create(payload)

    try:
        yield

    except Exception:
        commit.statuses.create({**payload, "state": "failed"})

        raise

    state = "success" if workflow.status == WorkflowStatus.SUCCESS else "failed"

    commit.statuses.create({**payload, "state": state})


def get_wrapper_for_trigger_type(
    session: Session,
    workflow: Workflow,
    access_token: str,
) -> AbstractAsyncContextManager[None]:
    if session.trigger.type == "git.push":
        return wrap_in_gitlab_status_check(session, workflow, access_token)

    return nullcontext()


async def run_workflow(
    session: Session,
    terminal: TerminalSession,
    cloned_repo: Path,
    filenode: FileNode,
    workflow: Workflow,
    *,
    access_token: str,
    di: DiContainer,
) -> None:
    wrapper = get_wrapper_for_trigger_type(session, workflow, access_token)

    try:
        async with wrapper:
            executor_type = ExecutionSettings().executor

            ctx = get_execution_type(executor_type)(
                trigger=session.trigger,
                terminal=terminal,
                cloned_repo=cloned_repo,
                workflow=workflow,
            )

            if isinstance(ctx, RemoteDockerLikeExecutionContext):
                ctx.session_repo = di.session_repo()
                ctx.session = session

            exit_code = await ctx.run(filenode)

            workflow.finish(exit_code_to_status_code(exit_code))

    except Exception:
        workflow.finish(WorkflowStatus.FAILURE)

        raise


async def gather_issue_workflows(
    trigger: Trigger,
    cloned_repo: Path,
    access_token: str,
) -> list[FileNode]:
    user, repo = url_get_user_and_repo(trigger.repository_url)

    gl = gitlab.Gitlab(oauth_token=access_token)

    project = gl.projects.get(f"{user}/{repo}", lazy=True)
    commit = project.commits.get("HEAD")

    trigger.sha = GitSha(str(commit.get_id()))

    return await gather_workflows(trigger, cloned_repo, access_token)


async def gather_workflows(
    trigger: Trigger,
    cloned_repo: Path,
    access_token: str,
) -> list[FileNode]:
    username, repo_name = url_get_user_and_repo(trigger.repository_url)

    url = gitlab_clone_url(username, repo_name, access_token)

    assert trigger.sha

    files_or_errors = await repo_get_ci_files(
        url,
        str(trigger.sha),
        trigger,
        cloned_repo,
    )

    return [x for x in files_or_errors if not isinstance(x, AstError)]
