import asyncio
from asyncio import Task, create_task
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from cicada.api.application.session.rerun_session import RerunSession
from cicada.api.application.session.stop_session import StopSession
from cicada.api.common.json import asjson
from cicada.api.domain.session import SessionStatus
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser, get_user_from_jwt
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


@router.post("/api/session/{session_id}/stop")
async def stop_session(session_id: UUID, di: Di, user: CurrentUser) -> None:
    cmd = StopSession(di.session_repo(), di.session_terminators())

    await cmd.handle(session_id, user)


TASK_QUEUE: set[Task[None]] = set()


@router.post("/api/session/{session_id}/rerun")
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


@router.get("/api/session/{uuid}/session_info")
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


@router.get("/api/session/recent")
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


@router.websocket("/ws/session/watch_status")
async def websocket_endpoint(
    websocket: WebSocket, di: Di
) -> None:  # pragma: no cover
    """
    Open a websocket to listen for status updates for certain sessions. Once
    connected, the user sends their JWT token to authenticate, then they send
    a JSON array of string-encoded UUIDs for the sessions they want to listen
    to. Then, as the sessions start to finish, the session data will be
    returned to the user. Once all requested sessions have finished the
    websocket will close.

    This probably should be replaced with a pub-sub implementation that will
    handle all of this for me.
    """

    try:
        await websocket.accept()

        # TODO: add timeout here
        jwt = await websocket.receive_text()

        user = get_user_from_jwt(di.user_repo(), jwt)

        if not user:
            await websocket.send_json(
                {"error": "Websocket connection failed: Unauthorized"}
            )
            return await websocket.close()

        # TODO: add timeout here
        # TODO: limit size of JSON payload
        data = await websocket.receive_json()

        try:
            session_ids = {UUID(x) for x in data}
        except (TypeError, ValueError):
            await websocket.send_json(
                {"error": "Invalid JSON, expected array of UUIDs"}
            )
            return await websocket.close()

        session_repo = di.session_repo()

        while session_ids:
            for session_id in session_ids.copy():
                session = session_repo.get_session_by_session_id(
                    session_id, user=user
                )

                if not session:
                    session_ids.remove(session_id)

                if session and session.status != SessionStatus.PENDING:
                    session_ids.remove(session_id)

                    await websocket.send_json(asjson(session))

            await asyncio.sleep(1)

        await websocket.close()

    except WebSocketDisconnect:
        pass
