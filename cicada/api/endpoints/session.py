import asyncio
from asyncio import CancelledError, InvalidStateError, Task, create_task
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from websockets.exceptions import ConnectionClosed

from cicada.api.endpoints.di import Di
from cicada.api.endpoints.login_util import CurrentUser, get_user_from_jwt
from cicada.api.endpoints.task_queue import TaskQueue
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
from cicada.api.infra.notifications.send_email import send_email
from cicada.application.exceptions import CicadaException
from cicada.application.notifications.send_notification import SendNotification
from cicada.application.session.rerun_session import RerunSession
from cicada.application.session.stop_session import StopSession
from cicada.application.session.stream_session import StreamSession
from cicada.common.json import asjson
from cicada.domain.notification import Notification
from cicada.domain.session import Session, SessionId, SessionStatus

router = APIRouter()


@router.post("/api/session/{session_id}/stop")
async def stop_session(
    session_id: SessionId, di: Di, user: CurrentUser
) -> None:
    cmd = StopSession(di.session_repo(), di.session_terminators())

    await cmd.handle(session_id, user)


TASK_QUEUE = TaskQueue()


@router.post("/api/session/{session_id}/rerun")
async def rerun_session(
    session_id: SessionId, di: Di, user: CurrentUser
) -> None:
    # TODO: move to application
    # TODO: test this

    session_repo = di.session_repo()

    # TODO: ensure this fails if user doesnt have write access
    session = session_repo.get_session_by_session_id(
        session_id, user=user, permission="write"
    )

    if not session:
        return

    provider = session.trigger.provider

    if provider == "github":
        gather = gather_github_git_push_workflows

        async def workflow_wrapper(*args: Any) -> None:  # type: ignore[misc]
            await run_github_workflow(*args, di=di)  # type: ignore

    elif provider == "gitlab":
        gather = gather_gitlab_workflows
        workflow_wrapper = run_gitlab_workflow  # type: ignore
    else:
        assert False

    cmd = RerunSession(
        session_repo,
        di.terminal_session_repo(),
        gather_workflows=gather,
        workflow_runner=workflow_wrapper,
        env_repo=di.environment_repo(),
        repository_repo=di.repository_repo(),
        secret_repo=di.secret_repo(),
    )

    async def run(old_session: Session) -> None:
        session = await cmd.handle(old_session)

        if not (user and session and session.status.is_failure()):
            return

        email_cmd = SendNotification(send_email)

        await email_cmd.handle(
            Notification(type="email", user=user, session=session)
        )

    TASK_QUEUE.add(run(session))


@router.get("/api/session/{uuid}/session_info")
async def get_session_info(
    uuid: SessionId,
    di: Di,
    user: CurrentUser,
    # TODO: test query
    run: int = -1,
) -> JSONResponse:
    # TODO: test failure if user cannot see session

    session = di.session_repo().get_session_by_session_id(
        uuid, run, user, permission="read"
    )

    if session:
        return JSONResponse(asjson(session))

    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/api/session/recent")
async def get_recent_sessions(
    di: Di,
    user: CurrentUser,
    repo: str = "",
    session: SessionId | None = None,
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
async def watch_status(
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
        # TODO: pull from header instead
        jwt = await websocket.receive_text()

        user = get_user_from_jwt(di.user_repo(), jwt)

        if not user:
            await websocket.send_json(
                {"error": "Websocket connection failed: Unauthorized"}
            )
            return await websocket.close(code=1001)

        # TODO: add timeout here
        # TODO: limit size of JSON payload
        data = await websocket.receive_json()

        try:
            session_ids = {SessionId(x) for x in data}

        except (TypeError, ValueError):
            await websocket.send_json(
                {"error": "Invalid JSON, expected array of UUIDs"}
            )
            return await websocket.close()

        session_repo = di.session_repo()

        while session_ids:
            for session_id in session_ids.copy():
                session = session_repo.get_session_by_session_id(
                    session_id, user=user, permission="read"
                )

                if not session:
                    session_ids.remove(session_id)

                if session and session.status != SessionStatus.PENDING:
                    session_ids.remove(session_id)

                    await websocket.send_json(asjson(session))

            await asyncio.sleep(1)

        await websocket.close()

    except (WebSocketDisconnect, ConnectionClosed):
        pass


@router.websocket("/ws/session/{uuid}")
async def stream_session(
    uuid: SessionId,
    websocket: WebSocket,
    di: Di,
    run: int = -1,
) -> None:  # pragma: no cover
    task: Task[None] | None = None

    try:
        await websocket.accept()

        # TODO: add timeout here
        jwt = await websocket.receive_text()

        session_repo = di.session_repo()

        user = get_user_from_jwt(di.user_repo(), jwt)
        session = session_repo.get_session_by_session_id(uuid)

        if not (
            user
            and session
            and session_repo.can_user_access_session(
                user, session, permission="read"
            )
        ):
            await websocket.send_json(
                {"error": "You do not have access to this session"}
            )
            await websocket.close(code=1001)
            return

        async def stop_session() -> None:
            cmd = StopSession(session_repo, di.session_terminators())

            try:
                await cmd.handle(uuid, user)

            except CicadaException as exc:
                await websocket.send_json({"error": str(exc)})

        stream = StreamSession(
            di.terminal_session_repo(),
            session_repo,
            stop_session,
        )

        async def command_sender() -> None:
            async for command in websocket.iter_text():
                stream.send_command(command)

        task = create_task(command_sender())

        async for data in stream.stream(uuid, run):
            await websocket.send_json(data)

    except (WebSocketDisconnect, ConnectionClosed):
        return

    except RuntimeError:
        # A RuntimeError is thrown whenever trying to send data after the
        # websocket is disconnected. There is no good way to detect this since
        # uvicorn wraps the websocket connection, and the actual state of the
        # websocket is not forwarded.

        pass

    finally:
        if task:
            task.cancel()

            try:
                task.result()

            except (CancelledError, InvalidStateError):
                pass

            except (WebSocketDisconnect, ConnectionClosed):
                return

    await websocket.close()
