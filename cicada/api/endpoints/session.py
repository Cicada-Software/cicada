from asyncio import Task, create_task
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from cicada.api.application.session.rerun_session import RerunSession
from cicada.api.application.session.stop_session import StopSession
from cicada.api.common.json import asjson
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser
from cicada.api.infra.github.common import (
    gather_workflows_via_trigger as gather_github_git_push_workflows,
)
from cicada.api.infra.github.workflows import (
    run_workflow as run_github_workflow,
)
from cicada.api.infra.gitlab.workflows import (
    gather_workflows as gather_gitlab_workflows,
)
from cicada.api.infra.gitlab.workflows import (
    run_workflow as run_gitlab_workflow,
)

router = APIRouter()


@router.post("/session/{session_id}/stop")
async def stop_session(session_id: UUID, di: Di, user: CurrentUser) -> None:
    cmd = StopSession(di.session_repo(), di.session_terminators())

    await cmd.handle(session_id, user)


TASK_QUEUE: set[Task[None]] = set()


@router.post("/session/{session_id}/rerun")
async def rerun_session(session_id: UUID, di: Di, user: CurrentUser) -> None:
    # TODO: move to application
    # TODO: test this

    session_repo = di.session_repo()

    # TODO: test failure if user cannot see session
    session = session_repo.get_session_by_session_id(session_id, user=user)

    if not session:
        return

    provider = session.trigger.provider

    if provider == "github":
        gather = gather_github_git_push_workflows
        run = run_github_workflow
    elif provider == "gitlab":
        gather = gather_gitlab_workflows
        run = run_gitlab_workflow
    else:
        assert False

    cmd = RerunSession(
        session_repo,
        di.terminal_session_repo(),
        gather_workflows=gather,
        workflow_runner=run,
        env_repo=di.environment_repo(),
        repository_repo=di.repository_repo(),
    )

    task = create_task(cmd.handle(session))

    TASK_QUEUE.add(task)
    task.add_done_callback(TASK_QUEUE.discard)


@router.get("/session/{uuid}/session_info")
async def get_session_info(
    uuid: UUID,
    di: Di,
    user: CurrentUser,
    # TODO: test query
    run: int = -1,
) -> JSONResponse:
    # TODO: test failure if user cannot see session

    if session := di.session_repo().get_session_by_session_id(uuid, run, user):
        return JSONResponse(asjson(session))

    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/session/recent")
async def get_recent_sessions(
    di: Di,
    user: CurrentUser,
    repo: str = "",
    session: UUID | None = None,
) -> JSONResponse:
    session_repo = di.session_repo()

    if repo:
        recent = session_repo.get_recent_sessions_for_repo(
            user, repository_url=repo
        )

    elif session:
        recent = session_repo.get_runs_for_session(user, session)

    else:
        recent = session_repo.get_recent_sessions(user)

    return JSONResponse([asjson(session) for session in recent])
