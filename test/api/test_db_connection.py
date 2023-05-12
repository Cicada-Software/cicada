import os
import sqlite3
from unittest.mock import patch

import pytest

from cicada.api.infra.db_connection import DbConnection


def test_env_var_not_set_causes_exception() -> None:
    with (
        pytest.raises(ValueError, match="must be defined"),
        patch.dict(os.environ, {}, clear=True),
    ):
        DbConnection()


def test_env_var_set_will_be_used() -> None:
    with (
        patch("sqlite3.connect") as p,
        patch.dict(os.environ, {"DB_URL": "filename"}, clear=True),
    ):
        DbConnection()

    assert p.call_args[0][0] == "filename"


def test_explicitly_passed_filename_will_be_used_if_passed() -> None:
    db = sqlite3.connect(":memory:")

    with patch.dict(os.environ, {"DB_URL": "from_env"}, clear=True):
        db_connection = DbConnection(db)

        assert db_connection.conn is db
