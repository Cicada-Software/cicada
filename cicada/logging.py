import logging
from contextlib import suppress
from os import getenv
from pathlib import Path
from typing import Any, Final

from dotenv import load_dotenv

COLORS: Final = {
    logging.DEBUG: "\x1b[38;5;40m\x1b[48;5;232m",
    logging.WARNING: "\x1b[38;5;232m\x1b[48;5;214m",
    logging.ERROR: "\x1b[48;5;124m",
    logging.CRITICAL: "\x1b[1m\x1b[48;5;196m",
}


class CustomFormatter(logging.Formatter):
    datefmt = "%Y-%m-%dT%H:%M:%S"

    fmt: str
    project_root: Path

    def __init__(self, **kwargs: Any) -> None:  # type: ignore[misc]
        super().__init__(**kwargs)

        self.project_root = Path(__file__).parent.parent.parent

        self.fmt = " ".join(
            [
                "[%(asctime)s.%(msecs)d]",
                "[%(levelname)s]",
                "[%(pathname)s:%(lineno)d]:",
                "%(message)s",
            ]
        )

    def format(self, record: logging.LogRecord) -> str:
        color = COLORS.get(record.levelno, "")

        log_source = Path(record.pathname)

        with suppress(ValueError):
            record.pathname = str(log_source.relative_to(self.project_root))

        fmt = f"{color}{self.fmt}\x1b[0m"

        return logging.Formatter(fmt, datefmt=self.datefmt).format(record)


def setup() -> None:
    load_dotenv()

    handler = logging.StreamHandler()
    handler.setFormatter(CustomFormatter())

    log_level = getenv("CICADA_LOG_LEVEL", "WARNING").upper()

    logger = logging.getLogger("cicada")
    logger.setLevel(log_level)
    logger.addHandler(handler)
