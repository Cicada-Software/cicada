from asyncio import CancelledError, InvalidStateError, Task, create_task
from typing import Annotated
from uuid import UUID

from fastapi import (
    FastAPI,
    Form,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from websockets.exceptions import ConnectionClosed

from cicada.api.application.exceptions import CicadaException
from cicada.api.application.session.stop_session import StopSession
from cicada.api.application.session.stream_session import StreamSession
from cicada.api.endpoints.di import Di
from cicada.api.endpoints.env import router as env_router
from cicada.api.endpoints.installation import router as installation_router
from cicada.api.endpoints.login import router as login_router
from cicada.api.endpoints.login_util import CurrentUser, get_user_from_jwt
from cicada.api.endpoints.session import router as session_router
from cicada.api.middleware import (
    SlowRequestMiddleware,
    UnhandledExceptionHandler,
    cicada_exception_handler,
)
from cicada.api.settings import GitProviderSettings

app = FastAPI()
app.mount("/static", StaticFiles(directory="frontend/static"), "static")
app.include_router(login_router)
app.include_router(session_router)
app.include_router(env_router)
app.include_router(installation_router)
app.add_middleware(UnhandledExceptionHandler)
app.add_middleware(SlowRequestMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=512)
app.add_exception_handler(CicadaException, cicada_exception_handler)


ENABLED_PROVIDERS = GitProviderSettings().enabled_providers

if "github" in ENABLED_PROVIDERS:
    from cicada.api.endpoints.sso.github import router as github_sso_router
    from cicada.api.endpoints.webhook.github.main import (
        router as github_webhook_router,
    )

    app.include_router(github_webhook_router)
    app.include_router(github_sso_router)

if "gitlab" in ENABLED_PROVIDERS:
    from cicada.api.endpoints.webhook.gitlab.main import (
        router as gitlab_webhook_router,
    )

    app.include_router(gitlab_webhook_router)


# TODO: move to session router
@app.websocket("/ws/session/{uuid}")
async def websocket_endpoint(
    uuid: UUID,
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
            and session_repo.can_user_see_session(user, session)
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


@app.get("/runs")
async def runs_index() -> FileResponse:
    return FileResponse("./frontend/runs.html")


@app.get("/run/{uuid}")
async def run_index(uuid: UUID) -> FileResponse:
    return FileResponse("./frontend/run.html")


@app.get("/dashboard")
async def dashboard() -> FileResponse:
    return FileResponse("./frontend/dashboard.html")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("./frontend/landing.html")


@app.get("/settings")
async def settings() -> FileResponse:
    return FileResponse("./frontend/settings.html")


@app.get("/installation/{uuid}")
async def installation(uuid: UUID) -> FileResponse:
    return FileResponse("./frontend/installation.html")


@app.get("/repo/{_:path}")
async def repo(_: str) -> FileResponse:
    return FileResponse("./frontend/repo.html")


@app.get("/api/ping")
async def ping(_: CurrentUser) -> str:
    """
    A simple heartbeat. Can be used for checking if the user has access to the
    current page, for example.
    """

    return "pong"


@app.post("/api/join_waitlist")
async def join_waitlist(di: Di, email: Annotated[str, Form()] = "") -> None:
    try:
        di.waitlist_repo().insert_email(email)

    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
