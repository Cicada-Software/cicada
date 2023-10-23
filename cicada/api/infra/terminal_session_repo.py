from cicada.api.infra.db_connection import DbConnection
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.session import WorkflowId
from cicada.domain.terminal_session import TerminalSession

# TODO: move to class (as singleton)
LIVE_TERMINAL_SESSIONS = dict[WorkflowId, TerminalSession]()


class TerminalSessionRepo(ITerminalSessionRepo, DbConnection):
    def append_to_workflow(self, workflow_id: WorkflowId, data: bytes) -> None:
        self.conn.execute(
            """
            INSERT INTO terminal_sessions (workflow_uuid, lines)
            VALUES (?, ?)
            ON CONFLICT
            DO UPDATE SET lines=lines || excluded.lines;
            """,
            [workflow_id, data],
        )

        self.conn.commit()

    def get_by_workflow_id(self, workflow_id: WorkflowId) -> TerminalSession | None:
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

    def create(self, workflow_id: WorkflowId) -> TerminalSession:
        terminal = TerminalSession()

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
