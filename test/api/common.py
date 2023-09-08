import sqlite3

from cicada.api.infra.migrate import migrate


class SqliteTestWrapper:
    connection: sqlite3.Connection | None = None
    migrated_connection: sqlite3.Connection | None = None

    @classmethod
    def _setup(cls) -> None:
        if cls.connection is None:
            cls.reset()

    @classmethod
    def reset(cls) -> None:
        """Refresh the datasources used for testing."""

        if cls.migrated_connection is None:
            cls.migrated_connection = sqlite3.connect(":memory:")

            migrate(cls.migrated_connection)

        if cls.connection:
            cls.connection.executescript(
                """
                DELETE FROM sessions;
                DELETE FROM terminal_sessions;
                DELETE FROM triggers;
                DELETE FROM repositories;
                DELETE FROM _user_repos;
                DELETE FROM waitlist;
                DELETE FROM env_vars;
                DELETE FROM users WHERE username != 'admin';
                DELETE FROM installations;
                DELETE FROM _installation_users;
                DELETE FROM secrets;
                """
            )
            cls.connection.commit()

        else:
            cls.connection = sqlite3.connect(
                ":memory:", check_same_thread=False
            )

            cls.migrated_connection.backup(cls.connection)
