import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from cicada.api.infra.db_connection import DbConnection
from cicada.common.json import asjson
from cicada.domain.datetime import UtcDatetime
from cicada.domain.repo.repository_repo import Permission
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.session import (
    Run,
    Session,
    SessionId,
    SessionStatus,
    Status,
    Workflow,
)
from cicada.domain.triggers import GitSha, Trigger, json_to_trigger
from cicada.domain.user import User


class SessionRepo(ISessionRepo, DbConnection):
    # TODO: finished_at is never added?
    def create(self, session: Session) -> None:
        trigger = asjson(session.trigger)

        # Remove env vars and secrets from trigger since they contain sensitive
        # information, and will bloat the size of the trigger.
        del trigger["env"]
        del trigger["secret"]

        cursor = self.conn.cursor()

        # TODO: don't reinsert trigger for re-ran sessions
        trigger_id = self.conn.execute(
            "INSERT INTO triggers (trigger, data) VALUES (?, ?);",
            [
                session.trigger.type,
                json.dumps(trigger, separators=(",", ":")),
            ],
        ).lastrowid

        assert trigger_id

        cursor.execute(
            """
            INSERT INTO sessions (
                uuid,
                status,
                started_at,
                trigger,
                trigger_id,
                run_number,
                run_on_self_hosted
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            [
                session.id,
                session.status.name,
                session.started_at,
                session.trigger.type,
                trigger_id,
                session.run,
                int(session.run_on_self_hosted),
            ],
        )

        cursor.execute(
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
                rerun_number,
                run_on_self_hosted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            [
                uuid4(),
                session.id,
                session.status.name,
                str(session.trigger.sha),
                "",
                session.started_at,
                session.finished_at,
                session.run,
                1,
                int(session.run_on_self_hosted),
            ],
        )

        self.conn.commit()

    def update(self, session: Session) -> None:
        cursor = self.conn.cursor()

        cursor.execute(
            """
            UPDATE sessions SET
                status=?,
                finished_at=?
            WHERE uuid=? AND run_number=?;
            """,
            [
                session.status.name,
                session.finished_at,
                session.id,
                session.run,
            ],
        )

        cursor.execute(
            """
            UPDATE workflows SET
                status=?,
                finished_at=?
            WHERE session_id=? AND run_number=?;
            """,
            [
                session.status.name,
                session.finished_at,
                session.id,
                session.run,
            ],
        )

        self.conn.commit()

    # TODO: test with run param
    # TODO: test user param
    def get_session_by_session_id(
        self,
        uuid: SessionId,
        run: int = -1,
        user: User | None = None,
        *,
        permission: Permission | None = None,
    ) -> Session | None:
        if bool(user) ^ bool(permission):
            raise ValueError('"user" and "permission" must be used together')

        trigger = self._get_trigger(uuid)

        if not trigger:
            return None

        cursor = self.conn.cursor()

        if run == -1:
            cursor.execute(
                """
                SELECT
                    status,
                    started_at,
                    finished_at,
                    run_number,
                    run_on_self_hosted
                FROM sessions
                WHERE uuid=?
                ORDER BY run_number DESC
                LIMIT 1;
                """,
                [uuid],
            )

        else:
            cursor.execute(
                """
                SELECT
                    status,
                    started_at,
                    finished_at,
                    run_number,
                    run_on_self_hosted
                FROM sessions
                WHERE uuid=? AND run_number=?;
                """,
                [uuid, run],
            )

        if row := cursor.fetchone():
            session = Session(
                id=uuid,
                status=SessionStatus(row["status"]),
                started_at=UtcDatetime.fromisoformat(row["started_at"]),
                finished_at=(
                    UtcDatetime.fromisoformat(row["finished_at"])
                    if row["finished_at"]
                    else None
                ),
                trigger=trigger,
                run=row["run_number"],
                run_on_self_hosted=bool(row["run_on_self_hosted"]),
            )

            if not user or self.can_user_access_session(
                user,
                session,
                permission=permission,  # type: ignore
            ):
                return session

        return None

    def get_recent_sessions(self, user: User) -> list[Session]:
        if user.is_admin:
            return self.get_recent_sessions_as_admin()

        rows = self.conn.execute(
            """
            SELECT
                session_uuid,
                session_status,
                session_started_at,
                session_finished_at,
                MAX(session_run),
                trigger_data,
                session_run_on_self_hosted
            FROM v_user_sessions
            WHERE user_uuid=?
            GROUP BY session_uuid
            ORDER BY session_started_at DESC;
            """,
            [user.id],
        ).fetchall()

        return [self._convert(x) for x in rows]

    def get_recent_sessions_for_repo(
        self, user: User, repository_url: str
    ) -> list[Session]:
        if user.is_admin:
            rows = self.conn.execute(
                """
                SELECT
                    s.uuid,
                    s.status,
                    s.started_at,
                    s.finished_at,
                    MAX(s.run_number),
                    t.data,
                    session_run_on_self_hosted
                FROM sessions s
                JOIN triggers t ON t.id = s.trigger_id
                WHERE t.data->>'repository_url'=?
                GROUP BY s.uuid
                ORDER BY s.started_at DESC;
                """,
                [repository_url],
            ).fetchall()

        else:
            rows = self.conn.execute(
                """
                SELECT
                    session_uuid,
                    session_status,
                    session_started_at,
                    session_finished_at,
                    MAX(session_run),
                    trigger_data,
                    session_run_on_self_hosted
                FROM v_user_sessions
                WHERE user_uuid=? AND repo_url=?
                GROUP BY session_uuid
                ORDER BY session_started_at DESC;
                """,
                [user.id, repository_url],
            ).fetchall()

        return [self._convert(x) for x in rows]

    def get_runs_for_session(
        self,
        user: User,
        uuid: SessionId,
    ) -> list[Session]:
        if user.is_admin:
            rows = self.conn.execute(
                """
                SELECT
                    s.uuid,
                    s.status,
                    s.started_at,
                    s.finished_at,
                    s.run_number,
                    t.data,
                    run_on_self_hosted
                FROM sessions s
                JOIN triggers t ON t.id = s.trigger_id
                WHERE s.uuid=?
                ORDER BY s.started_at DESC;
                """,
                [uuid],
            ).fetchall()

        else:
            rows = self.conn.execute(
                """
                SELECT
                    session_uuid,
                    session_status,
                    session_started_at,
                    session_finished_at,
                    session_run,
                    trigger_data,
                    session_run_on_self_hosted
                FROM v_user_sessions
                WHERE user_uuid=? AND session_uuid=?
                ORDER BY session_started_at DESC;
                """,
                [user.id, uuid],
            ).fetchall()

        return [self._convert(x) for x in rows]

    def get_recent_sessions_as_admin(self) -> list[Session]:
        rows = self.conn.execute(
            """
            SELECT
                s.uuid,
                s.status,
                s.started_at,
                s.finished_at,
                MAX(s.run_number),
                t.data,
                s.run_on_self_hosted
            FROM sessions s
            JOIN triggers t ON t.id = s.trigger_id
            GROUP BY uuid
            ORDER BY started_at DESC;
            """
        ).fetchall()

        return [self._convert(x) for x in rows]

    def can_user_access_session(
        self,
        user: User,
        session: Session,
        *,
        permission: Permission,
    ) -> bool:
        return self._can_user_access_session_id(
            user,
            session.id,
            permission=permission,
        )

    def _can_user_access_session_id(
        self,
        user: User,
        session_id: SessionId,
        *,
        permission: Permission,
    ) -> bool:
        if user.is_admin:
            return True

        if permission == "read":
            rows = self.conn.execute(
                """
                SELECT repo_is_public
                FROM v_user_sessions
                WHERE session_uuid=?
                """,
                [session_id],
            ).fetchone()

            if rows and rows["repo_is_public"]:
                return True

        rows = self.conn.execute(
            """
            SELECT repo_perms
            FROM v_user_sessions
            WHERE session_uuid=? AND user_uuid=?
            """,
            [session_id, user.id],
        ).fetchone()

        if not rows or not rows[0]:
            return False

        permission_levels = ["read", "write", "owner"]

        required_level = permission_levels.index(permission)

        return any(
            permission_levels.index(p) >= required_level
            for p in rows[0].split(",")
        )

    def get_runs_for_session2(self, user: User, uuid: SessionId) -> list[Run]:
        if not self._can_user_access_session_id(user, uuid, permission="read"):
            return []

        rows = self.conn.execute(
            """
            SELECT
                uuid,
                status,
                sha,
                filename,
                started_at,
                finished_at,
                run_number,
                run_on_self_hosted
            FROM workflows
            WHERE session_id = ?;
            """,
            [uuid],
        ).fetchall()

        if not rows:
            return []

        runs: list[Run] = []

        for row in rows:
            workflow = Workflow(
                id=row["uuid"],
                filename=Path(row["filename"]),
                sha=GitSha(row["sha"]),
                status=Status(row["status"]),
                started_at=UtcDatetime.fromisoformat(row["started_at"]),
                finished_at=(
                    UtcDatetime.fromisoformat(row["finished_at"])
                    if row["finished_at"]
                    else None
                ),
                run_on_self_hosted=bool(row["run_on_self_hosted"]),
            )

            runs.append(Run({workflow.filename: [workflow]}))

        return runs

    def _get_trigger(self, uuid: SessionId) -> Trigger | None:
        cursor = self.conn.execute(
            """
            SELECT t.trigger, t.data
            FROM sessions s
            JOIN triggers t ON t.id = s.trigger_id
            WHERE s.uuid = ?;
            """,
            [uuid],
        )

        if row := cursor.fetchone():
            return json_to_trigger(row[1])

        return None

    @staticmethod
    def _convert(row: sqlite3.Row) -> Session:
        return Session(
            id=SessionId(row[0]),
            status=SessionStatus(row[1]),
            started_at=UtcDatetime.fromisoformat(row[2]),
            finished_at=(
                UtcDatetime.fromisoformat(row[3]) if row[3] else None
            ),
            run=row[4],
            trigger=json_to_trigger(row[5]),
            run_on_self_hosted=bool(row[6]),
        )
