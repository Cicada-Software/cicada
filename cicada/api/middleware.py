import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from cicada.api.application.exceptions import (
    CicadaException,
    Forbidden,
    InvalidRequest,
    NotFound,
    Unauthorized,
)
from cicada.api.settings import NotificationSettings


class SlowRequestMiddleware:  # pragma: no cover
    """Warns whenever a slow request is made."""

    SLOW_REQUEST_THRESHOLD_SECONDS = 1.5

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] == "http":
            start = time.time()
            await self.app(scope, receive, send)
            elapsed = time.time() - start

            if elapsed > self.SLOW_REQUEST_THRESHOLD_SECONDS:
                path = scope.get("path", "<unknown>")

                logger = logging.getLogger("cicada")
                logger.warning(
                    "Request for `%s` was slow (%f seconds)", path, elapsed
                )

        else:
            await self.app(scope, receive, send)


async def cicada_exception_handler(
    _: Request, exc: CicadaException
) -> JSONResponse:
    if isinstance(exc, InvalidRequest):
        code = 400
    elif isinstance(exc, Unauthorized):
        code = 401
    elif isinstance(exc, Forbidden):
        code = 403
    elif isinstance(exc, NotFound):
        code = 404
    else:
        code = 500

    return JSONResponse({"detail": str(exc)}, status_code=code)


class UnhandledExceptionHandler:  # pragma: no cover
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        try:
            await self.app(scope, receive, send)

        except Exception:
            import httpx

            settings = NotificationSettings()

            if settings.is_enabled:
                async with httpx.AsyncClient() as client:
                    # TODO: extract this so it can be used elsewhere

                    msg = "Unhandled exception on Cicada production server"

                    try:
                        resp = await client.post(
                            settings.url,
                            headers={
                                "Title": "Unhandled Exception Occurred",
                                "Priority": "urgent",
                            },
                            content=msg,
                        )

                        ok = resp.status_code == 200

                    except httpx.HTTPError:
                        ok = False

                if not ok:
                    logger = logging.getLogger("cicada")
                    logger.critical("Could not send exception notification")

            raise
