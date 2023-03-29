import sqlite3

from cicada.api.infra.migrate import get_version, migrate


def test_migration() -> None:
    db = sqlite3.connect(":memory:")

    # First migration, shouldn't fail
    migrate(db)

    old_version = get_version(db)

    # Second migration, should not update anything
    migrate(db)

    assert old_version == get_version(db)
