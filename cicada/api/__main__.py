# pragma: no cover

from pathlib import Path

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from cicada.api.settings import verify_env_vars
from cicada.logging import setup as setup_logging

setup_logging()


def run_setup_wizard() -> None:
    from cicada.api.setup import app

    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104


def run_live_site() -> None:
    from cicada.api.main import app
    from cicada.api.settings import DNSSettings

    settings = DNSSettings()

    # include timestamps in uvicorn logs
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )


if Path(".env").exists():
    verify_env_vars()

    run_live_site()

else:
    run_setup_wizard()
