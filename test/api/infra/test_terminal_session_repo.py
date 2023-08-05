from uuid import uuid4

from cicada.api.infra.terminal_session_repo import (
    LIVE_TERMINAL_SESSIONS,
    TerminalSessionRepo,
)
from test.api.common import SqliteTestWrapper


class TestTerminalSessionRepo(SqliteTestWrapper):
    repo: TerminalSessionRepo

    @classmethod
    def setup_class(cls) -> None:
        super().reset()

        cls.repo = TerminalSessionRepo(cls.connection)

    def test_create_and_get_terminal_session(self) -> None:
        session_id = uuid4()

        new_terminal_session = self.repo.create(session_id)

        assert new_terminal_session is self.repo.get_by_session_id(session_id)

    def test_get_terminal_session_that_has_finished(self) -> None:
        session_id = uuid4()

        terminal_session = self.repo.create(session_id)

        self.repo.append_to_session(session_id, b"line 1\r\n")
        self.repo.append_to_session(session_id, b"line 2\r\n")
        self.repo.append_to_session(session_id, b"line 3\n")
        self.repo.append_to_session(session_id, b"line 4\n")

        # TODO: this is an ugly hack, makes things harder to test
        LIVE_TERMINAL_SESSIONS.clear()

        received_terminal_session = self.repo.get_by_session_id(session_id)

        assert received_terminal_session
        assert received_terminal_session.is_done

        chunks = [
            b"line 1\r\n",
            b"line 2\r\n",
            b"line 3\n",
            b"line 4\n",
        ]

        assert received_terminal_session.chunks == [b"".join(chunks)]

        # This might be an implementation detail, because if the terminal
        # session is "done", the original one should be able to be returned
        # with no issue. The fact that we recreate it from the DB (only because
        # it does not exist in memory) smells fishy to me.
        assert received_terminal_session is not terminal_session

    def test_get_terminal_session_that_doesnt_exist(self) -> None:
        assert not self.repo.get_by_session_id(uuid4())
