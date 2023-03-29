# pragma: no cover

import logging

import uvicorn

from cicada.api.logging import CustomFormatter
from cicada.api.main import app
from cicada.api.settings import DNSSettings

handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())

logger = logging.getLogger("cicada")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

settings = DNSSettings()

uvicorn.run(
    app,
    host=settings.host,
    port=settings.port,
)
