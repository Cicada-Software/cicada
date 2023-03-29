import json
from uuid import UUID

from cicada.api.common.datetime import UtcDatetime
from cicada.api.common.json import asjson
from cicada.api.domain.session import Session, SessionStatus
from cicada.api.domain.triggers import Trigger, json_to_trigger
from cicada.api.domain.user import User
from cicada.api.infra.db_connection import DbConnection
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
                str(session.id),
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
                str(session.id),
                session.run,
            ],
        )

        self.conn.commit()

    # TODO: test with run param
    # TODO: test user param
    def get_session_by_session_id(
        self,
        uuid: UUID,
        run: int = -1,
        user: User | None = None,
    ) -> Session | None:
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
                [str(uuid)],
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
                [str(uuid), run],
            )

        if row := cursor.fetchone():
            assert trigger

            session = Session(
                id=uuid,
                status=SessionStatus(row[0]),
                started_at=UtcDatetime.fromisoformat(row[1]),
                finished_at=(
                    UtcDatetime.fromisoformat(row[2]) if row[2] else None
                ),
                trigger=trigger,
                run=row[3],
            )

            if not user or self.can_user_see_session(user, session):
                return session

        return None

    def get_recent_sessions(self, user: User) -> list[Session]:
        return self._get_recent_sessions(
            is_admin=user.is_admin, username=user.username
        )

    def get_recent_sessions_for_repo(
        self, user: User, repository_url: str
    ) -> list[Session]:
        return self._get_recent_sessions(
            is_admin=user.is_admin,
            username=user.username,
            repository_url=repository_url,
        )

    def get_runs_for_session(
        self,
        user: User,
        uuid: UUID,
    ) -> list[Session]:
        return self._get_recent_sessions(
            is_admin=user.is_admin,
            username=user.username,
            session_id=uuid,
        )

    def get_recent_sessions_as_admin(self) -> list[Session]:
        return self._get_recent_sessions(is_admin=True)

    def can_user_see_session(self, user: User, session: Session) -> bool:
        if user.is_admin:
            return True

        can_see = self.conn.execute(
            """
            SELECT EXISTS (
                SELECT u.id
                FROM _user_repos ur
                JOIN repositories r ON r.id = ur.repo_id
                JOIN users u ON u.id = ur.user_id
                JOIN triggers t ON t.data->>'repository_url' = r.url
                JOIN sessions s ON s.trigger_id = t.id
                WHERE s.uuid=? AND u.username=? AND u.platform=?
            );
            """,
            [str(session.id), user.username, user.provider],
        ).fetchone()[0]

        return bool(can_see)

    def _get_recent_sessions(
        self,
        is_admin: bool = False,
        username: str = "",
        repository_url: str = "",
        session_id: UUID | None = None,
    ) -> list[Session]:
        # TODO: move user authorization into application service
        # TODO: add a limit, try not to fetch all sessions at once

        if is_admin and not any((repository_url, session_id)):
            rows = self.conn.execute(
                """
                SELECT
                    s.uuid,
                    s.status,
                    s.started_at,
                    s.finished_at,
                    max(s.run_number),
                    t.data
                FROM sessions s
                JOIN triggers t ON t.id = s.trigger_id
                GROUP BY uuid
                ORDER BY started_at DESC;
                """
            ).fetchall()

        else:
            if session_id:
                run_number = "s.run_number"
                group_by = ""
            else:
                run_number = "max(s.run_number)"
                group_by = "GROUP BY s.uuid"

            rows = self.conn.execute(
                f"""
                SELECT
                    s.uuid,
                    s.status,
                    s.started_at,
                    s.finished_at,
                    {run_number},
                    t.data
                FROM _user_repos ur
                JOIN repositories r ON r.id = ur.repo_id
                JOIN users u ON u.id = ur.user_id
                JOIN triggers t ON t.data->>'repository_url' = r.url
                JOIN sessions s ON s.trigger_id = t.id
                WHERE (
                    (? OR u.username = ?)
                    AND (
                        ?
                        OR (r.url = ?)
                        OR (s.uuid = ?)
                    )
                )
                {group_by}
                ORDER BY s.started_at DESC;
                """,
                [
                    is_admin,
                    username,
                    not any((repository_url, session_id)),
                    repository_url,
                    str(session_id or ""),
                ],
            ).fetchall()

        sessions: list[Session] = []

        for row in rows:
            sessions.append(
                Session(
                    id=UUID(row[0]),
                    status=SessionStatus(row[1]),
                    started_at=UtcDatetime.fromisoformat(row[2]),
                    finished_at=(
                        UtcDatetime.fromisoformat(row[3]) if row[3] else None
                    ),
                    run=row[4],
                    trigger=json_to_trigger(row[5]),
                )
            )

        return sessions

    def _get_trigger(self, uuid: UUID) -> Trigger | None:
        cursor = self.conn.execute(
            """
            SELECT t.trigger, t.data
            FROM sessions s
            JOIN triggers t ON t.id = s.trigger_id
            WHERE s.uuid = ?;
            """,
            [str(uuid)],
        )

        if row := cursor.fetchone():
            return json_to_trigger(row[1])

        return None
