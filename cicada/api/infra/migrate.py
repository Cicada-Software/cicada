import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Any
from uuid import uuid4

from passlib.context import CryptContext

from cicada.api.settings import MigrationSettings

migration_queue = []

Migration = Callable[[sqlite3.Connection], None]


def auto_migrate(version: int) -> Callable[[Migration], Migration]:
    def outer(migration: Migration) -> Migration:
        @wraps(migration)
        def inner(db: sqlite3.Connection) -> None:
            migration(db)
            db.commit()

            if get_version(db) == 0:
                db.executescript(
                    """
                    CREATE TABLE _migration_version (version int NOT NULL);

                    INSERT INTO _migration_version VALUES (1);
                    """
                )

            else:
                db.execute(
                    "UPDATE _migration_version SET version = (?);",
                    [version],
                )

            db.commit()

        migration_queue.append((version, inner))

        return inner

    return outer


@auto_migrate(version=1)
def migrate_v1(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL,
            git_sha TEXT,
            status TEXT NOT NULL DEFAULT 'SUCCESS'
        );

        CREATE TABLE git_commits (
            -- repo_url TEXT NOT NULL,
            sha TEXT NOT NULL,
            author_username TEXT NOT NULL,
            commit_message TEXT NOT NULL,
            committed_on TEXT NOT NULL
        );

        CREATE TABLE terminal_sessions (
            session_id TEXT PRIMARY KEY NOT NULL,
            lines TEXT NOT NULL
        );
        """
    )


@auto_migrate(version=2)
def migrate_v2(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE sessions ADD COLUMN started_at TEXT NOT NULL;
        ALTER TABLE sessions ADD COLUMN finished_at TEXT;
        """
    )


@auto_migrate(version=3)
def migrate_v3(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE git_commits
        ADD COLUMN repository TEXT NOT NULL
        DEFAULT 'dosisod/cicada2';
        """
    )


@auto_migrate(version=4)
def migrate_v4(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        UPDATE sessions
        SET status='FAILURE'
        WHERE finished_at IS NOT NULL AND status='PENDING';
        """
    )


@auto_migrate(version=5)
def migrate_v5(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE sessions
        ADD COLUMN trigger TEXT NOT NULL
        DEFAULT 'git.push';
        """
    )


@auto_migrate(version=6)
def migrate_v6(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            -- TODO: use internal repo id instead of repo URL
            repo_url TEXT NOT NULL,
            platform_id TEXT NOT NULL,
            title TEXT NOT NULL,
            -- TODO: use author table instead of username
            submitted_by TEXT NOT NULL,
            is_locked INTEGER NOT NULL,
            opened_at TEXT NOT NULL,
            body TEXT NOT NULL
        );
        """
    )


@auto_migrate(version=7)
def migrate_v7(db: sqlite3.Connection) -> None:
    db.executescript("ALTER TABLE sessions ADD COLUMN issue_id INTEGER NULL;")


@auto_migrate(version=8)
def migrate_v8(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE issues ADD COLUMN provider TEXT NOT NULL DEFAULT 'github';
        """
    )


@auto_migrate(version=9)
def migrate_v9(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger TEXT NOT NULL,
            data TEXT NOT NULL
        );

        ALTER TABLE sessions ADD COLUMN trigger_id INTEGER NOT NULL;
        """
    )


@auto_migrate(version=10)
def migrate_v10(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            hash TEXT NOT NULL
        );
        """
    )

    pw = MigrationSettings().default_admin_password
    hash = CryptContext(schemes=["bcrypt"]).hash(pw)

    db.execute("INSERT INTO users (username, hash) VALUES (?, ?);", ["admin", hash])


@auto_migrate(version=11)
def migrate_v11(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE sessions DROP COLUMN git_sha;
        ALTER TABLE sessions DROP COLUMN issue_id;
        """
    )


@auto_migrate(version=12)
def migrate_v12(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE github_sso_tokens (
            username TEXT NOT NULL,
            access_token TEXT NOT NULL,
            access_token_expires_at TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            refresh_token_expires_at TEXT NOT NULL,
            token_type TEXT NOT NULL,
            scope TEXT NOT NULL
        );
        """
    )


@auto_migrate(version=13)
def migrate_v13(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            url TEXT NOT NULL
        );

        CREATE TABLE _user_repos (
            user_id INTEGER NOT NULL,
            repo_id INTEGER NOT NULL,
            perms TEXT NOT NULL
        );

        ALTER TABLE users
        ADD COLUMN is_admin INTEGER NOT NULL
        DEFAULT 0;

        ALTER TABLE users
        ADD COLUMN platform TEXT NOT NULL
        DEFAULT 'cicada';

        UPDATE users
        SET is_admin=1, platform='cicada'
        WHERE username='admin';
        """
    )


@auto_migrate(version=14)
def migrate_v14(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE UNIQUE INDEX ux_repositories_provider_url
        ON repositories(provider, url);

        CREATE UNIQUE INDEX ux_users_username_provider
        ON users(username, platform);
        """
    )


@auto_migrate(version=15)
def migrate_v15(db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT * FROM triggers;").fetchall()

    for row in rows:
        id: int = row[0]
        trigger: str = row[1]
        data: dict[str, Any] = json.loads(row[2])  # type: ignore[misc]

        if trigger == "git.push":
            repository_url = data.pop("repository")
        elif trigger == "issue.open":
            repository_url = data.pop("repo_url")
        else:
            assert False

        data["repository_url"] = repository_url

        db.execute(
            "UPDATE triggers SET data=? WHERE id=?",
            [json.dumps(data), id],
        )


@auto_migrate(version=16)
def migrate_v16(db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT * FROM triggers;").fetchall()

    for row in rows:
        id: int = row[0]
        trigger: str = row[1]
        data: dict[str, Any] = json.loads(row[2])  # type: ignore[misc]

        data["type"] = trigger

        db.execute(
            "UPDATE triggers SET data=? WHERE id=?",
            [json.dumps(data), id],
        )


@auto_migrate(version=17)
def migrate_v17(db: sqlite3.Connection) -> None:
    """
    Grab all unique indexes from table, remove all rows, add unique constraint,
    and then add all the unique rows back in.
    """

    rows = db.execute("SELECT DISTINCT * FROM _user_repos;").fetchall()

    db.executescript(
        """
        DELETE FROM _user_repos;

        CREATE UNIQUE INDEX IF NOT EXISTS ux_user_repos_user_id_repo_id
        ON _user_repos(user_id, repo_id);
        """
    )

    for row in rows:
        user_id: int = row[0]
        repo_id: int = row[1]
        perms: str = row[2]

        db.execute(
            """
            INSERT INTO _user_repos (user_id, repo_id, perms)
            VALUES (?, ?, ?);
            """,
            [user_id, repo_id, perms],
        )


@auto_migrate(version=18)
def migrate_v18(db: sqlite3.Connection) -> None:
    def normalize_utc_timezones(date: str) -> str:
        """
        Convert an ambiguous UTC datetime into an actual UTC datetime.
        Basically any datetime without a timezone is assumed to be a UTC
        datetime. For non UTC datetimes the offset will be kept in the form
        "±XX:YY". For UTC timezones, the "+00:00" will be replaced with "Z" to
        optimize string length.
        """

        if date.endswith("UTC"):
            # specifically for parsing Gitlab datetimes
            return str(
                datetime.strptime(date, "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            ).replace("+00:00", "Z")

        if date.endswith("Z"):
            date.replace("Z", "+00:00")

        d = datetime.fromisoformat(date)

        if not d.tzinfo:
            d = d.replace(tzinfo=timezone.utc)

        return str(d).replace("+00:00", "Z")

    rows = db.execute("SELECT * FROM triggers;")

    for row in rows:
        id: int = row[0]
        data: dict[str, Any] = json.loads(row[2])  # type: ignore[misc]

        datetime_fields = ("committed_on", "opened_at", "closed_at")

        for k, v in data.items():
            if k in datetime_fields:
                data[k] = normalize_utc_timezones(v)

        db.execute(
            "UPDATE triggers SET data=? WHERE id=?",
            [json.dumps(data, separators=(",", ":")), id],
        )


@auto_migrate(version=19)
def migrate_v19(db: sqlite3.Connection) -> None:
    db.executescript("DROP TABLE github_sso_tokens;")


@auto_migrate(version=20)
def migrate_v20(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE waitlist (
            submitted_at TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );
        """
    )


@auto_migrate(version=21)
def migrate_v21(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE users
        ADD COLUMN uuid TEXT NOT NULL DEFAULT 'invalid';
        """
    )

    users = db.execute("SELECT id FROM users;").fetchall()

    for (user_id,) in users:
        db.execute("UPDATE users SET uuid=? WHERE id=?", [str(uuid4()), user_id])

    db.commit()

    assert (
        db.execute(
            """
        SELECT COUNT(id)
        FROM users
        WHERE uuid='invalid';
        """
        ).fetchone()[0]
        == 0
    )

    db.executescript("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_uuid ON users(uuid);")

    db.commit()


@auto_migrate(version=22)
def migrate_v22(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        DROP TABLE git_commits;

        DROP TABLE issues;
        """
    )


@auto_migrate(version=23)
def migrate_v23(db: sqlite3.Connection) -> None:
    db.execute(
        """
        ALTER TABLE sessions
        ADD COLUMN run_number INTEGER NOT NULL DEFAULT 1;
        """
    )


@auto_migrate(version=24)
def migrate_v24(db: sqlite3.Connection) -> None:
    db.execute("UPDATE terminal_sessions SET session_id=session_id || '#1';")


@auto_migrate(version=25)
def migrate_v25(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE env_vars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL
        );

        CREATE UNIQUE INDEX ux_env_vars_repo_id_key
        ON env_vars(repo_id, key);
        """
    )


@auto_migrate(version=26)
def migrate_v26(db: sqlite3.Connection) -> None:
    db.execute(
        """
        ALTER TABLE env_vars
        ADD COLUMN "order" INTEGER NOT NULL DEFAULT 0;
        """
    )


@auto_migrate(version=27)
def migrate_v27(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE triggers
        SET data=json_insert(data, '$.ref', 'refs/heads/master')
        WHERE trigger = 'git.push';
        """
    )


@auto_migrate(version=28)
def migrate_v28(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE users ADD COLUMN last_login TEXT;")


@auto_migrate(version=29)
def migrate_v29(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE installations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            scope TEXT NOT NULL
        );

        CREATE UNIQUE INDEX ux_installations_name_provider
        ON installations(name, provider);

        CREATE TABLE _installation_users (
            installation_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            perms TEXT NOT NULL
        );

        CREATE UNIQUE INDEX ux_installation_users
        ON _installation_users(installation_id, user_id);
        """
    )


@auto_migrate(version=30)
def migrate_v30(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE installations
        ADD COLUMN provider_id TEXT NOT NULL
        DEFAULT '';

        ALTER TABLE installations
        ADD COLUMN provider_url TEXT NOT NULL
        DEFAULT '';

        DROP INDEX ux_installations_name_provider;

        CREATE UNIQUE INDEX ux_installations_provider_info
        ON installations(name, provider, provider_id, provider_url);
        """
    )


@auto_migrate(version=31)
def migrate_v31(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE VIEW v_user_sessions AS
        SELECT
            u.id AS user_id,
            u.uuid AS user_uuid,
            u.username AS username,
            u.platform AS user_provider,
            r.id AS repo_id,
            r.url AS repo_url,
            s.id AS session_id,
            s.uuid AS session_uuid,
            s.status AS session_status,
            s.started_at AS session_started_at,
            s.finished_at AS session_finished_at,
            s.run_number AS session_run,
            t.data AS trigger_data
        FROM _user_repos ur
        JOIN repositories r ON r.id = ur.repo_id
        JOIN users u ON u.id = ur.user_id
        JOIN triggers t ON t.data->>'repository_url' = r.url
        JOIN sessions s ON s.trigger_id = t.id;
        """
    )


@auto_migrate(version=32)
def migrate_v32(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        DROP VIEW v_user_sessions;

        CREATE VIEW v_user_sessions AS
        SELECT
            u.id AS user_id,
            u.uuid AS user_uuid,
            u.username AS username,
            u.platform AS user_provider,
            r.id AS repo_id,
            r.url AS repo_url,
            ur.perms AS repo_perms,
            s.id AS session_id,
            s.uuid AS session_uuid,
            s.status AS session_status,
            s.started_at AS session_started_at,
            s.finished_at AS session_finished_at,
            s.run_number AS session_run,
            t.data AS trigger_data
        FROM _user_repos ur
        JOIN repositories r ON r.id = ur.repo_id
        JOIN users u ON u.id = ur.user_id
        JOIN triggers t ON t.data->>'repository_url' = r.url
        JOIN sessions s ON s.trigger_id = t.id;
        """
    )


@auto_migrate(version=33)
def migrate_v33(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE _installation_repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            installation_id INTEGER NOT NULL,
            repo_id INTEGER NOT NULL
        );

        CREATE UNIQUE INDEX ux_installation_repos_ids
        ON _installation_repos(installation_id, repo_id);

        CREATE VIEW v_session_runtime_metrics AS
        SELECT
            i.id AS installation_id,
            i.uuid AS installation_uuid,
            s.id AS session_id,
            s.uuid AS session_uuid,
            s.status AS session_status,
            s.started_at AS session_started_at,
            s.finished_at AS session_finished_at,
            s.run_number AS session_run,
            r.id AS repo_id,
            iif(
                s.finished_at IS NULL,
                -1,
                unixepoch(s.finished_at) - unixepoch(s.started_at)
            ) AS seconds
        FROM sessions s
        JOIN triggers t ON t.id = s.trigger_id
        JOIN repositories r ON r.url = t.data->>'repository_url'
        JOIN _installation_repos ir ON ir.repo_id = r.id
        JOIN installations i ON i.id = ir.installation_id
        """
    )


@auto_migrate(version=34)
def migrate_v34(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE repositories
        ADD COLUMN is_public INTEGER NOT NULL
        DEFAULT 0;

        DROP VIEW v_user_sessions;

        CREATE VIEW v_user_sessions AS
        SELECT
            u.id AS user_id,
            u.uuid AS user_uuid,
            u.username AS username,
            u.platform AS user_provider,
            r.id AS repo_id,
            r.url AS repo_url,
            r.is_public AS repo_is_public,
            ur.perms AS repo_perms,
            s.id AS session_id,
            s.uuid AS session_uuid,
            s.status AS session_status,
            s.started_at AS session_started_at,
            s.finished_at AS session_finished_at,
            s.run_number AS session_run,
            t.data AS trigger_data
        FROM _user_repos ur
        JOIN repositories r ON r.id = ur.repo_id
        JOIN users u ON u.id = ur.user_id
        JOIN triggers t ON t.data->>'repository_url' = r.url
        JOIN sessions s ON s.trigger_id = t.id;
        """
    )


@auto_migrate(version=35)
def migrate_v35(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            status TEXT NOT NULL,
            sha TEXT NOT NULL,
            filename TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NULL,
            run_number INT NOT NULL,
            rerun_number INT NOT NULL
        );
        """
    )

    sessions = db.execute(
        """
        SELECT
            uuid,
            status,
            started_at,
            finished_at,
            trigger,
            trigger_id,
            run_number
        FROM sessions;
        """
    ).fetchall()

    for session in sessions:
        db.execute(
            """
            INSERT INTO workflows (
                uuid,
                session_id,
                status,
                sha,
                filename,
                started_at,
                finished_at,
                run_number,
                rerun_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            [
                str(uuid4()),
                session["uuid"],
                session["status"],
                session["trigger"],
                "",
                session["started_at"],
                session["finished_at"],
                session["run_number"],
                1,
            ],
        )

    db.commit()


@auto_migrate(version=36)
def migrate_v36(db: sqlite3.Connection) -> None:
    db.executescript("ALTER TABLE users ADD COLUMN email TEXT;")


@auto_migrate(version=37)
def migrate_v37(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE runners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            installation_uuid TEXT NOT NULL,
            secret TEXT NOT NULL,
            groups TEXT NOT NULL
        );
        """
    )


@auto_migrate(version=38)
def migrate_v38(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE sessions
        ADD COLUMN run_on_self_hosted INT NOT NULL DEFAULT 0;

        ALTER TABLE workflows
        ADD COLUMN run_on_self_hosted INT NOT NULL DEFAULT 0;

        DROP VIEW v_user_sessions;

        CREATE VIEW v_user_sessions AS
        SELECT
            u.id AS user_id,
            u.uuid AS user_uuid,
            u.username AS username,
            u.platform AS user_provider,
            r.id AS repo_id,
            r.url AS repo_url,
            r.is_public AS repo_is_public,
            ur.perms AS repo_perms,
            s.id AS session_id,
            s.uuid AS session_uuid,
            s.status AS session_status,
            s.started_at AS session_started_at,
            s.finished_at AS session_finished_at,
            s.run_number AS session_run,
            t.data AS trigger_data,
            s.run_on_self_hosted as session_run_on_self_hosted
        FROM _user_repos ur
        JOIN repositories r ON r.id = ur.repo_id
        JOIN users u ON u.id = ur.user_id
        JOIN triggers t ON t.data->>'repository_url' = r.url
        JOIN sessions s ON s.trigger_id = t.id;
        """
    )


@auto_migrate(version=39)
def migrate_v39(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE cache_objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            repository_url TEXT NOT NULL,
            key TEXT NOT NULL,
            session_id INT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


@auto_migrate(version=40)
def migrate_v40(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            repo_id INTEGER NULL,
            installation_uuid NULL,
            updated_at TEXT NOT NULL,
            key TEXT NOT NULL,
            ciphertext TEXT NOT NULL
        );

        CREATE UNIQUE INDEX ux_secrets
        ON secrets (
            scope,
            IFNULL(repo_id, -1),
            IFNULL(installation_uuid, ''),
            key
        );
        """
    )


@auto_migrate(version=41)
def migrate_v41(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE sessions
        ADD COLUMN title TEXT NULL;

        ALTER TABLE workflows
        ADD COLUMN title TEXT NULL;

        DROP VIEW v_user_sessions;

        CREATE VIEW v_user_sessions AS
        SELECT
            u.id AS user_id,
            u.uuid AS user_uuid,
            u.username AS username,
            u.platform AS user_provider,
            r.id AS repo_id,
            r.url AS repo_url,
            r.is_public AS repo_is_public,
            ur.perms AS repo_perms,
            s.id AS session_id,
            s.uuid AS session_uuid,
            s.status AS session_status,
            s.started_at AS session_started_at,
            s.finished_at AS session_finished_at,
            s.run_number AS session_run,
            t.data AS trigger_data,
            s.run_on_self_hosted as session_run_on_self_hosted,
            s.title as session_title
        FROM _user_repos ur
        JOIN repositories r ON r.id = ur.repo_id
        JOIN users u ON u.id = ur.user_id
        JOIN triggers t ON t.data->>'repository_url' = r.url
        JOIN sessions s ON s.trigger_id = t.id;
        """
    )


@auto_migrate(version=42)
def migrate_v42(db: sqlite3.Connection) -> None:
    # TODO: this could probably be cleaned up, but since this was created
    # incrementally it is easier to keep it as it is (ie, creating a column
    # just to delete/rename it later).

    db.executescript(
        """
        ALTER TABLE terminal_sessions
        ADD COLUMN workflow_uuid TEXT NOT NULL DEFAULT '';
        """
    )

    rows = db.execute(
        """
        SELECT
            wf.uuid AS workflow_uuid,
            ts.session_id AS session_id
        FROM terminal_sessions ts
        JOIN workflows wf
            ON wf.session_id = SUBSTR(ts.session_id, 0, 37)
            AND wf.run_number = SUBSTR(ts.session_id, 38);
        """
    ).fetchall()

    for workflow_id, session_id in rows:
        db.execute(
            """
            UPDATE terminal_sessions SET workflow_uuid=? WHERE session_id=?;
            """,
            [workflow_id, session_id],
        )

    db.executescript(
        """
        UPDATE terminal_sessions SET session_id=workflow_uuid;
        ALTER TABLE terminal_sessions DROP COLUMN workflow_uuid;
        ALTER TABLE terminal_sessions
            RENAME COLUMN session_id TO workflow_uuid;
        """
    )


@auto_migrate(version=43)
def migrate_v43(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        ALTER TABLE workflows DROP COLUMN rerun_number;
        ALTER TABLE workflows ADD COLUMN parent TEXT NULL;
        """
    )


@auto_migrate(version=44)
def migrate_v44(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        DROP VIEW v_user_sessions;

        CREATE VIEW v_user_sessions AS
        SELECT
            u.id AS user_id,
            u.uuid AS user_uuid,
            u.username AS username,
            u.platform AS user_provider,
            r.id AS repo_id,
            r.url AS repo_url,
            r.is_public AS repo_is_public,
            ur.perms AS repo_perms,
            s.id AS session_id,
            s.uuid AS session_uuid,
            s.status AS session_status,
            s.started_at AS session_started_at,
            s.finished_at AS session_finished_at,
            s.run_number AS session_run,
            t.data AS trigger_data,
            s.title as session_title
        FROM _user_repos ur
        JOIN repositories r ON r.id = ur.repo_id
        JOIN users u ON u.id = ur.user_id
        JOIN triggers t ON t.data->>'repository_url' = r.url
        JOIN sessions s ON s.trigger_id = t.id;

        ALTER TABLE sessions DROP COLUMN run_on_self_hosted;
        """
    )


@auto_migrate(version=45)
def migrate_v45(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        DELETE FROM cache_objects;

        ALTER TABLE cache_objects DROP COLUMN session_id;
        ALTER TABLE cache_objects ADD COLUMN workflow_id TEXT NOT NULL;
        """
    )


@auto_migrate(version=46)
def migrate_v46(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        DROP VIEW v_user_sessions;

        CREATE VIEW v_user_sessions AS
        SELECT
            u.id AS user_id,
            u.uuid AS user_uuid,
            u.username AS username,
            u.platform AS user_provider,
            r.id AS repo_id,
            r.url AS repo_url,
            r.is_public AS repo_is_public,
            ur.perms AS repo_perms,
            s.id AS session_id,
            s.uuid AS session_uuid,
            s.status AS session_status,
            s.started_at AS session_started_at,
            s.finished_at AS session_finished_at,
            s.run_number AS session_run,
            t.data AS trigger_data
        FROM _user_repos ur
        JOIN repositories r ON r.id = ur.repo_id
        JOIN users u ON u.id = ur.user_id
        JOIN triggers t ON t.data->>'repository_url' = r.url
        JOIN sessions s ON s.trigger_id = t.id;

        ALTER TABLE sessions DROP COLUMN title;
        """
    )


@auto_migrate(version=47)
def migrate_v47(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        UPDATE workflows
        SET sha=x.sha
        FROM (
            SELECT w2.uuid AS workflow_id, t.data->>'sha' AS sha
            FROM workflows w2
            JOIN sessions s ON s.uuid = w2.session_id
            JOIN triggers t ON t.id = s.id
            WHERE LENGTH(w2.sha) < 10
        ) AS x
        WHERE uuid = x.workflow_id;
        """
    )


@auto_migrate(version=48)
def migrate_v48(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE gitlab_oauth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INT NOT NULL UNIQUE,
            expires_at INT NOT NULL,
            data TEXT NOT NULL
        );
        """
    )


@auto_migrate(version=49)
def migrate_v49(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE gitlab_repo_webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            created_by_user_id INT NOT NULL,
            project_id INT NOT NULL,
            hook_id INT NOT NULL,
            hashed_secret TEXT NOT NULL
        );
        """
    )


def get_version(db: sqlite3.Connection) -> int:
    try:
        version = db.execute("SELECT version FROM _migration_version;").fetchone()[0]

        return int(version)

    except sqlite3.OperationalError:
        return 0


def migrate(db: sqlite3.Connection) -> None:
    current_version = get_version(db)

    for migration_version, migration in migration_queue:
        if current_version < migration_version:
            migration(db)


if __name__ == "__main__":
    # TODO: allow this to be configured
    db = sqlite3.connect("./db.db3")
    db.row_factory = sqlite3.Row

    migrate(db)
