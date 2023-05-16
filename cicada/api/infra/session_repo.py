import json
import sqlite3

from cicada.api.common.datetime import UtcDatetime
from cicada.api.common.json import asjson
from cicada.api.domain.session import Session, SessionId, SessionStatus
from cicada.api.domain.triggers import Trigger, json_to_trigger
from cicada.api.domain.user import User
from cicada.api.infra.db_connection import DbConnection
from cicada.api.repo.repository_repo import Permission
from cicada.api.repo.session_repo import ISessionRepo


class SessionRepo(ISessionRepo, DbConnection):
    # TODO: finished_at is never added?
    def create(self, session: Session) -> None:
        trigger = asjson(session.trigger)

        # Remove env vars from the trigger because they will bloat the trigger
        # size, will be replaced with new values (if there are any) when reran,
        # and if there is a secret committed, it will be harder to remove.
        del trigger["env"]

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
                run_number
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            [
                session.id,
                session.status.name,
                session.started_at,
                session.trigger.type,
                trigger_id,
                session.run,
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
                    run_number
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
                    run_number
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
                trigger_data
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
                    t.data
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
                    trigger_data
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
                    t.data
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
                    trigger_data
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
                t.data
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
        if user.is_admin:
            return True

        if permission == "read":
            rows = self.conn.execute(
                """
                SELECT repo_is_public
                FROM v_user_sessions
                WHERE session_uuid=?
                """,
                [session.id],
            ).fetchone()

            if rows and rows["repo_is_public"]:
                return True

        rows = self.conn.execute(
            """
            SELECT repo_perms
            FROM v_user_sessions
            WHERE session_uuid=? AND user_uuid=?
            """,
            [session.id, user.id],
        ).fetchone()

        if not rows or not rows[0]:
            return False

        permission_levels = ["read", "write", "owner"]

        required_level = permission_levels.index(permission)

        return any(
            permission_levels.index(p) >= required_level
            for p in rows[0].split(",")
        )

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
        )
