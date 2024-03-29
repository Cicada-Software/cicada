import sqlite3
from uuid import UUID

from cicada.api.settings import DBSettings
from cicada.domain.datetime import Datetime, UtcDatetime

sqlite3.register_adapter(UtcDatetime, str)
sqlite3.register_adapter(Datetime, str)
sqlite3.register_adapter(UUID, str)


def get_default_db() -> sqlite3.Connection:
    return sqlite3.connect(DBSettings().db_url, check_same_thread=False)


class DbConnection:
    conn: sqlite3.Connection

    def __init__(self, db: sqlite3.Connection | None = None) -> None:
        self.conn = get_default_db() if db is None else db

        self.conn.row_factory = sqlite3.Row
