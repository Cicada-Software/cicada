from cicada.api.infra.db_connection import DbConnection
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.session import SessionId, WorkflowId
from cicada.domain.terminal_session import TerminalSession

# TODO: move to class (as singleton)
LIVE_TERMINAL_SESSIONS = dict[WorkflowId, TerminalSession]()


class TerminalSessionRepo(ITerminalSessionRepo, DbConnection):
    def append_to_session(
        self, session_id: SessionId, data: bytes, run: int = -1
    ) -> None:
        if run == -1:
            run = self._get_run_count_for_session(session_id)

        cursor = self.conn.cursor()

        workflow_id = self._get_workflow_id(session_id, run)
        assert workflow_id

        cursor.execute(
            """
            INSERT INTO terminal_sessions (workflow_uuid, lines)
            VALUES (?, ?)
            ON CONFLICT
            DO UPDATE SET lines=lines || excluded.lines;
            """,
            [workflow_id, data],
        )

        self.conn.commit()

    def get_by_session_id(
        self, session_id: SessionId, run: int = -1
    ) -> TerminalSession | None:
        if run == -1:
            run = self._get_run_count_for_session(session_id)

        workflow_id = self._get_workflow_id(session_id, run)

        if not workflow_id:
            return None

        if terminal := LIVE_TERMINAL_SESSIONS.get(workflow_id):
            return terminal

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT lines FROM terminal_sessions WHERE workflow_uuid=?;
            """,
            [workflow_id],
        )

        if rows := cursor.fetchone():
            terminal = TerminalSession()
            terminal.chunks = [rows[0].encode()]
            terminal.finish()

            return terminal

        return None

    def create(self, session_id: SessionId, run: int = -1) -> TerminalSession:
        terminal = TerminalSession()

        if run == -1:
            run = self._get_run_count_for_session(session_id) + 1

        workflow_id = self._get_workflow_id(session_id, run)
        assert workflow_id

        LIVE_TERMINAL_SESSIONS[workflow_id] = terminal

        self.conn.execute(
            """
            INSERT INTO terminal_sessions (workflow_uuid, lines)
            VALUES (?, '')
            """,
            [workflow_id],
        )
        self.conn.commit()

        return terminal

    def _get_run_count_for_session(self, session_id: SessionId) -> int:
        run = self.conn.execute(
            """
            SELECT MAX(s.run_number)
            FROM terminal_sessions ts
            JOIN workflows w ON w.uuid=ts.workflow_uuid
            JOIN sessions s
                ON s.uuid=w.session_id
                AND s.run_number=w.run_number
            WHERE s.uuid=?;
            """,
            [session_id],
        ).fetchone()[0]

        return run or 0

    def _get_workflow_id(
        self,
        session_id: SessionId,
        run_number: int,
    ) -> WorkflowId | None:
        # TODO: placeholder until user passes workflow ID instead of session.
        # Ideally this repo will have nothing to do with sessions, just
        # workflows.

        row = self.conn.execute(
            """
            SELECT uuid FROM workflows
            WHERE session_id=? AND run_number=?;
            """,
            [session_id, run_number],
        ).fetchone()

        return WorkflowId(row[0]) if row else None
