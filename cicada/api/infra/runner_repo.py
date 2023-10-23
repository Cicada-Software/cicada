import sqlite3
from collections import defaultdict
from typing import ClassVar
from uuid import UUID

from cicada.api.infra.db_connection import DbConnection
from cicada.ast.nodes import FileNode
from cicada.domain.password_hash import PasswordHash
from cicada.domain.repo.runner_repo import IRunnerRepo
from cicada.domain.runner import Runner, RunnerId
from cicada.domain.session import Session


class RunnerRepo(IRunnerRepo, DbConnection):
    session_queue: ClassVar[defaultdict[RunnerId, list[tuple[Session, FileNode, str]]]]

    def __init__(self, db: sqlite3.Connection | None = None) -> None:
        super().__init__(db)

        if not hasattr(self.__class__, "session_queue"):
            self.__class__.session_queue = defaultdict(list)

    def get_runner_by_id(self, id: RunnerId) -> Runner | None:
        runner = self.conn.execute(
            """
            SELECT
                uuid,
                installation_uuid,
                secret,
                groups
            FROM runners
            WHERE uuid=?;
            """,
            [id],
        ).fetchone()

        if runner is None:
            return runner

        return Runner(
            id=RunnerId(UUID(runner["uuid"])),
            installation_id=runner["installation_uuid"],
            secret=PasswordHash(runner["secret"]),
            groups=frozenset(runner["groups"].split(",") if runner["groups"] else ()),
        )

    def queue_session(
        self,
        session: Session,
        tree: FileNode,
        url: str,
    ) -> None:
        if runner_id := self._get_runner_id_for_session(session):
            self.session_queue[runner_id].append((session, tree, url))

    def get_queued_sessions_for_runner(self, id: RunnerId) -> list[tuple[Session, FileNode, str]]:
        try:
            return self.session_queue.pop(id)

        except KeyError:
            return []

    def _get_runner_id_for_session(self, session: Session) -> RunnerId | None:
        row = self.conn.execute(
            """
            SELECT ru.uuid
            FROM runners ru
            JOIN installations i ON i.uuid = ru.installation_uuid
            JOIN _installation_repos ir
                ON ir.installation_id = i.id
            JOIN repositories re ON re.id = ir.repo_id
            JOIN triggers t ON t.data->>'repository_url' = re.url
            JOIN sessions s ON s.trigger_id = t.id
            WHERE s.uuid = ?
            LIMIT 1;
            """,
            [session.id],
        ).fetchone()

        return None if id is None else RunnerId(UUID(row[0]))
