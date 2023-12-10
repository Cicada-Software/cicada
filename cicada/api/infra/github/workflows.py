from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext
from pathlib import Path

from cicada.api.di import DiContainer
from cicada.api.infra.common import url_get_user_and_repo
from cicada.api.infra.run_program import (
    ExecutionContext,
    RemoteDockerLikeExecutionContext,
    SelfHostedExecutionContext,
    exit_code_to_status_code,
    get_execution_type,
)
from cicada.api.settings import DNSSettings, ExecutionSettings
from cicada.ast.nodes import FileNode
from cicada.domain.datetime import UtcDatetime
from cicada.domain.session import Session, SessionStatus, Workflow, WorkflowStatus
from cicada.domain.terminal_session import TerminalSession
from cicada.domain.triggers import CommitTrigger, GitSha, IssueTrigger, Trigger

from .common import (
    add_access_token_for_repository_url,
    gather_workflows_via_trigger,
    get_github_integration_for_repo,
)


async def gather_issue_workflows(
    trigger: Trigger,
    cloned_repo: Path,
) -> list[FileNode]:  # pragma: no cover
    assert isinstance(trigger, IssueTrigger)

    username, repo_name = url_get_user_and_repo(trigger.repository_url)

    github = await get_github_integration_for_repo(username, repo_name)

    data = await github.rest.repos.async_get_commit(username, repo_name, "HEAD")
    commit = data.parsed_data

    trigger.sha = GitSha(commit.sha)

    return await gather_workflows_via_trigger(trigger, cloned_repo)


STATUS_TO_CHECK_RUN_STATUS: dict[SessionStatus, str] = {
    SessionStatus.PENDING: "pending",
    SessionStatus.FAILURE: "failure",
    SessionStatus.STOPPED: "cancelled",
    SessionStatus.SUCCESS: "success",
}


@asynccontextmanager
async def wrap_in_github_check_run(
    session: Session, workflow: Workflow
) -> AsyncGenerator[None, None]:  # pragma: no cover
    assert isinstance(session.trigger, CommitTrigger)

    username, repo = url_get_user_and_repo(session.trigger.repository_url)

    github = await get_github_integration_for_repo(username, repo)

    base_url = f"https://{DNSSettings().domain}"
    redirect_url = f"{base_url}/run/{session.id}?run={session.run}"

    data = await github.rest.checks.async_create(
        username,
        repo,
        name=workflow.title or "Cicada",
        head_sha=str(session.trigger.sha),
        external_id=str(workflow.id),
        details_url=f"{base_url}/api/github_sso_link?url={redirect_url}",
        status="in_progress",
        started_at=UtcDatetime.now(),
    )
    check_run_id = data.parsed_data.id

    try:
        yield

    except Exception:
        await github.rest.checks.async_update(
            username,
            repo,
            check_run_id,
            status="completed",
            conclusion="failure",
            completed_at=UtcDatetime.now(),
        )

        raise

    await github.rest.checks.async_update(
        username,
        repo,
        check_run_id,
        status="completed",
        conclusion=STATUS_TO_CHECK_RUN_STATUS[workflow.status],
        completed_at=UtcDatetime.now(),
    )


def get_wrapper_for_trigger_type(
    session: Session,
    workflow: Workflow,
) -> AbstractAsyncContextManager[None]:
    if session.trigger.type == "git.push":
        return wrap_in_github_check_run(session, workflow)

    return nullcontext()  # pragma: no cover


async def run_workflow(
    session: Session,
    terminal: TerminalSession,
    cloned_repo: Path,
    file: FileNode,
    workflow: Workflow,
    *,
    di: DiContainer,
) -> None:
    wrapper = get_wrapper_for_trigger_type(session, workflow)

    try:
        async with wrapper:
            if workflow.run_on_self_hosted:
                url = await add_access_token_for_repository_url(session.trigger.repository_url)

                ctx: ExecutionContext = SelfHostedExecutionContext(
                    trigger=session.trigger,
                    terminal=terminal,
                    cloned_repo=cloned_repo,
                    workflow=workflow,
                    session=session,
                    url=url,
                    session_repo=di.session_repo(),
                    runner_repo=di.runner_repo(),
                )

            else:
                executor_type = ExecutionSettings().executor

                ctx = get_execution_type(executor_type)(
                    # TODO: switch back to session instead of trigger
                    trigger=session.trigger,
                    terminal=terminal,
                    cloned_repo=cloned_repo,
                    workflow=workflow,
                )

                if isinstance(ctx, RemoteDockerLikeExecutionContext):
                    ctx.get_wrapper_for_trigger_type = get_wrapper_for_trigger_type
                    ctx.session_repo = di.session_repo()
                    ctx.terminal_repo = di.terminal_session_repo()
                    ctx.session = session

            exit_code = await ctx.run(file)

            workflow.finish(exit_code_to_status_code(exit_code))

    except Exception:
        workflow.finish(WorkflowStatus.FAILURE)

        raise
