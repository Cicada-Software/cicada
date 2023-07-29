from collections.abc import AsyncGenerator
from contextlib import (
    AbstractAsyncContextManager,
    asynccontextmanager,
    nullcontext,
)
from pathlib import Path

from githubkit import GitHub

from cicada.api.di import DiContainer
from cicada.api.infra.common import url_get_user_and_repo
from cicada.api.infra.run_program import (
    SelfHostedExecutionContext,
    exit_code_to_status_code,
    get_execution_type,
)
from cicada.api.settings import DNSSettings, ExecutionSettings
from cicada.ast.nodes import FileNode, RunType
from cicada.domain.datetime import UtcDatetime
from cicada.domain.session import Session, SessionStatus
from cicada.domain.terminal_session import TerminalSession
from cicada.domain.triggers import CommitTrigger, GitSha, IssueTrigger, Trigger

from .common import (
    gather_workflows_via_trigger,
    get_github_integration_for_repo,
    get_repo_access_token,
    github_clone_url,
)


async def gather_issue_workflows(
    trigger: Trigger,
    cloned_repo: Path,
) -> list[FileNode]:  # pragma: no cover
    assert isinstance(trigger, IssueTrigger)

    username, repo_name = url_get_user_and_repo(trigger.repository_url)

    github = await get_github_integration_for_repo(username, repo_name)

    data = await github.rest.repos.async_get_commit(
        username, repo_name, "HEAD"
    )
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
    session: Session, token: str
) -> AsyncGenerator[None, None]:  # pragma: no cover
    assert isinstance(session.trigger, CommitTrigger)

    username, repo = url_get_user_and_repo(session.trigger.repository_url)

    github = GitHub(token)

    data = await github.rest.checks.async_create(
        username,
        repo,
        name="Cicada",
        head_sha=str(session.trigger.sha),
        external_id=str(session.id),
        details_url=f"http://{DNSSettings().domain}/run/{session.id}",
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
        conclusion=STATUS_TO_CHECK_RUN_STATUS[session.status],
        completed_at=UtcDatetime.now(),
    )


async def run_workflow(
    session: Session,
    terminal: TerminalSession,
    cloned_repo: Path,
    filenode: FileNode,
    di: DiContainer | None = None,
) -> None:
    username, repo = url_get_user_and_repo(session.trigger.repository_url)

    access_token = await get_repo_access_token(username, repo)
    url = github_clone_url(username, repo, access_token)

    wrapper: AbstractAsyncContextManager[None]

    if session.trigger.type == "git.push":
        wrapper = wrap_in_github_check_run(session, access_token)
    else:
        wrapper = nullcontext()  # pragma: no cover

    try:
        async with wrapper:
            if not filenode.run_on or filenode.run_on.type == RunType.IMAGE:
                executor_type = ExecutionSettings().executor

                ctx = get_execution_type(executor_type)(
                    url=url,
                    trigger_type=session.trigger.type,
                    trigger=session.trigger,
                    session=session,
                    terminal=terminal,
                    cloned_repo=cloned_repo,
                )

            elif (
                filenode.run_on and filenode.run_on.type == RunType.SELF_HOSTED
            ):
                assert di

                ctx = SelfHostedExecutionContext(
                    url=url,
                    trigger_type=session.trigger.type,
                    trigger=session.trigger,
                    session=session,
                    terminal=terminal,
                    cloned_repo=cloned_repo,
                )

                # TODO: move to ctor
                ctx.session_repo = di.session_repo()
                ctx.runner_repo = di.runner_repo()

            else:
                assert False, "impossible"

            exit_code = await ctx.run()

            session.finish(exit_code_to_status_code(exit_code))

    except Exception:
        session.finish(SessionStatus.FAILURE)

        raise
