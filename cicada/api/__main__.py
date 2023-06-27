# pragma: no cover

import logging
from pathlib import Path

import uvicorn

from cicada.api.logging import CustomFormatter

handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())

logger = logging.getLogger("cicada")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)


def run_setup_wizard() -> None:
    from cicada.api.setup import app

    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104


def run_live_site() -> None:
    from cicada.api.main import app
    from cicada.api.settings import DNSSettings

    settings = DNSSettings()

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )


if Path(".env").exists():
    run_live_site()

else:
    run_setup_wizard()
