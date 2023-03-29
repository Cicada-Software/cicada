import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from cicada.api.application.exceptions import CicadaException, Unauthorized


class SlowRequestMiddleware:  # pragma: no cover
    "Warns whenever a slow request is made."

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
    if isinstance(exc, Unauthorized):  # noqa: SIM108
        code = 403
    else:
        code = 500

    return JSONResponse({"detail": str(exc)}, status_code=code)
