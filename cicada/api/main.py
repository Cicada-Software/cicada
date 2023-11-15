from typing import Annotated

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cicada.api.endpoints.di import Di
from cicada.api.endpoints.env import router as env_router
from cicada.api.endpoints.installation import router as installation_router
from cicada.api.endpoints.login import router as login_router
from cicada.api.endpoints.login_util import CurrentUser
from cicada.api.endpoints.runner import router as runner_router
from cicada.api.endpoints.secret import router as secret_router
from cicada.api.endpoints.session import router as session_router
from cicada.api.middleware import (
    DisableIframeMiddleware,
    SlowRequestMiddleware,
    UnhandledExceptionHandler,
    cicada_exception_handler,
)
from cicada.api.settings import GitProviderSettings
from cicada.application.exceptions import CicadaException
from cicada.domain.installation import InstallationId
from cicada.domain.session import SessionId

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(login_router)
app.include_router(session_router)
app.include_router(env_router)
app.include_router(installation_router)
app.include_router(runner_router)
app.include_router(secret_router)
app.add_middleware(UnhandledExceptionHandler)
app.add_middleware(SlowRequestMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=512)
app.add_middleware(DisableIframeMiddleware)
app.add_exception_handler(CicadaException, cicada_exception_handler)


ENABLED_PROVIDERS = GitProviderSettings().enabled_providers

if "github" in ENABLED_PROVIDERS:
    from cicada.api.endpoints.sso.github import router as github_sso_router
    from cicada.api.endpoints.webhook.github.main import router as github_webhook_router

    app.include_router(github_webhook_router)
    app.include_router(github_sso_router)

if "gitlab" in ENABLED_PROVIDERS:
    from cicada.api.endpoints.gitlab.projects import router as gitlab_projects_router
    from cicada.api.endpoints.sso.gitlab import router as gitlab_sso_router
    from cicada.api.endpoints.webhook.gitlab.main import router as gitlab_webhook_router

    app.include_router(gitlab_webhook_router)
    app.include_router(gitlab_sso_router)
    app.include_router(gitlab_projects_router)


@app.get("/runs")
async def runs_index() -> FileResponse:
    return FileResponse("./frontend/runs.html")


@app.get("/run/{_}")
async def run_index(_: SessionId) -> FileResponse:
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


@app.get("/terms")
async def terms() -> FileResponse:
    return FileResponse("./frontend/terms.html")


@app.get("/privacy")
async def privacy() -> FileResponse:
    return FileResponse("./frontend/privacy.html")


@app.get("/cookies")
async def cookies() -> FileResponse:
    return FileResponse("./frontend/cookies.html")


@app.get("/installation/{_}")
async def installation(_: InstallationId) -> FileResponse:
    return FileResponse("./frontend/installation.html")


@app.get("/repo/{_:path}")
async def repo(_: str) -> FileResponse:
    return FileResponse("./frontend/repo.html")


@app.get("/sitemap.xml")
async def sitemap() -> FileResponse:
    return FileResponse("./frontend/sitemap.xml")


@app.get("/robots.txt")
async def robots() -> FileResponse:
    return FileResponse("./frontend/robots.txt")


@app.get("/connect/gitlab")
async def gitlab_connect() -> FileResponse:
    return FileResponse("./frontend/connect/gitlab.html")


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


# The static files must be mounted after all the endpoints have been defined,
# otherwise the static files would take precedence.
app.mount("/", StaticFiles(directory="frontend/", html=True), "static")
