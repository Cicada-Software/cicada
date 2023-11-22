import json
import sqlite3
from pathlib import Path
from uuid import UUID

from cicada.api.infra.db_connection import DbConnection
from cicada.common.json import asjson
from cicada.domain.datetime import UtcDatetime
from cicada.domain.repo.repository_repo import Permission
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.session import Session, SessionId, SessionStatus, Status, Workflow, WorkflowId
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

        # TODO: don't reinsert trigger for re-ran sessions
        trigger_id = self.conn.execute(
            "INSERT INTO triggers (trigger, data) VALUES (?, ?);",
            [
                session.trigger.type,
                json.dumps(trigger, separators=(",", ":")),
            ],
        ).lastrowid

        assert trigger_id

        self.conn.execute(
            """
            INSERT INTO sessions (
                uuid,
                status,
                started_at,
                trigger,
                trigger_id,
                run_number
            ) VALUES (?, ?, ?, ?, ?, ?);
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

    def create_workflow(self, workflow: Workflow, session: Session) -> None:
        self.conn.execute(
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
                run_on_self_hosted,
                title,
                parent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            [
                workflow.id,
                session.id,
                workflow.status.name,
                str(workflow.sha),
                # TODO: disallow empty paths in Workflow object itself
                "" if workflow.filename == Path() else str(workflow.filename),
                workflow.started_at,
                workflow.finished_at,
                session.run,
                int(workflow.run_on_self_hosted),
                workflow.title,
                workflow.parent,
            ],
        )

        self.conn.commit()

    def update(self, session: Session) -> None:
        self.conn.execute(
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

    def update_workflow(self, workflow: Workflow) -> None:
        self.conn.execute(
            """
            UPDATE workflows SET
                status=?,
                finished_at=?
            WHERE uuid=?;
            """,
            [
                workflow.status.name,
                workflow.finished_at,
                workflow.id,
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

        if run == -1:
            row = self.conn.execute(
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
            ).fetchone()

        else:
            row = self.conn.execute(
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
            ).fetchone()

        if row:
            session = Session(
                id=uuid,
                status=SessionStatus(row["status"]),
                started_at=UtcDatetime.fromisoformat(row["started_at"]),
                finished_at=(
                    UtcDatetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
                ),
                trigger=trigger,
                run=row["run_number"],
            )

            session.runs = self._get_workflows_for_session(uuid)

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

        return [self._convert_session(x) for x in rows]

    def get_recent_sessions_for_repo(self, user: User, repository_url: str) -> list[Session]:
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

        return [self._convert_session(x) for x in rows]

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

        return [self._convert_session(x) for x in rows]

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

        return any(permission_levels.index(p) >= required_level for p in rows[0].split(","))

    def get_runs_for_session(
        self,
        user: User,
        uuid: SessionId,
    ) -> Session | None:
        if not self._can_user_access_session_id(user, uuid, permission="read"):
            return None

        workflows = self._get_workflows_for_session(uuid)

        # TODO: move to top, remove explicit access check
        session = self.get_session_by_session_id(
            uuid,
            user=user,
            permission="read",
        )
        assert session

        session.runs = workflows

        return session

    def _get_trigger(self, uuid: SessionId) -> Trigger | None:
        row = self.conn.execute(
            """
            SELECT t.data
            FROM sessions s
            JOIN triggers t ON t.id = s.trigger_id
            WHERE s.uuid = ?;
            """,
            [uuid],
        ).fetchone()

        return json_to_trigger(row[0]) if row else None

    @staticmethod
    def _convert_session(row: sqlite3.Row) -> Session:
        return Session(
            id=SessionId(row[0]),
            status=SessionStatus(row[1]),
            started_at=UtcDatetime.fromisoformat(row[2]),
            finished_at=(UtcDatetime.fromisoformat(row[3]) if row[3] else None),
            run=row[4],
            trigger=json_to_trigger(row[5]),
        )

    # TODO: return list of workflow ids
    def get_workflow_id_from_session(self, session: Session) -> WorkflowId | None:
        rows = self.conn.execute(
            """
            SELECT uuid FROM workflows WHERE session_id=? AND run_number=? AND parent is NULL;
            """,
            [session.id, session.run],
        ).fetchall()

        if not rows:
            return None

        assert len(rows) == 1

        return WorkflowId(UUID(rows[0][0]))

    def _get_workflows_for_session(self, uuid: SessionId) -> list[Workflow]:
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
                run_on_self_hosted,
                title,
                parent
            FROM workflows
            WHERE session_id=?
            ORDER BY run_number;
            """,
            [uuid],
        ).fetchall()

        workflows = [self._convert_workflow(row) for row in rows]

        tmp: dict[WorkflowId, Workflow] = {}

        # seed dict with all available workflows
        for workflow in workflows:
            tmp[workflow.id] = workflow

        # add sub workflows to parent workflows
        for workflow in workflows:
            if workflow.parent:
                tmp[workflow.parent].sub_workflows.append(workflow)

        # go through and remove non-root elements from the dict. Since parents still have
        # references to the sub-workflows, this will leave only the root nodes.
        for id, workflow in tmp.copy().items():
            if workflow.parent:
                tmp.pop(id)

        # since dicts retain insertion order, return values so that the workflows are ordered
        # by run number
        return list(tmp.values())

    # TODO: get subworkflows as well
    def get_workflow_by_id(self, uuid: WorkflowId) -> Workflow | None:
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
                run_on_self_hosted,
                title,
                parent
            FROM workflows
            WHERE uuid=?;
            """,
            [uuid],
        ).fetchall()

        if not rows:
            return None

        return self._convert_workflow(rows[0])

    @staticmethod
    def _convert_workflow(row: sqlite3.Row) -> Workflow:
        return Workflow(
            id=WorkflowId(UUID(row["uuid"])),
            filename=Path(row["filename"]),
            sha=GitSha(row["sha"]),
            status=Status(row["status"]),
            started_at=UtcDatetime.fromisoformat(row["started_at"]),
            finished_at=(
                UtcDatetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
            ),
            run_on_self_hosted=bool(row["run_on_self_hosted"]),
            title=row["title"] if row["title"] else None,
            parent=WorkflowId(UUID(row["parent"])) if row["parent"] else None,
        )
