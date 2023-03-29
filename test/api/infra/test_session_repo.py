from copy import deepcopy
from uuid import uuid4

from cicada.api.common.datetime import UtcDatetime
from cicada.api.domain.session import Session
from cicada.api.domain.triggers import CommitTrigger, GitSha
from cicada.api.domain.user import User
from cicada.api.infra.session_repo import SessionRepo
from test.api.common import SqliteTestWrapper


def create_dummy_session() -> Session:
    commit = CommitTrigger(
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="",
        message="",
        committed_on=UtcDatetime.now(),
        repository_url="https://github.com/user/repo",
        provider="github",
    )

    return Session(id=uuid4(), trigger=commit)


class TestSessionRepo(SqliteTestWrapper):
    session_repo: SessionRepo

    @classmethod
    def setup_class(cls) -> None:
        cls.reset()

    @classmethod
    def reset(cls) -> None:
        super().reset()

        cls.session_repo = SessionRepo(cls.connection)

    def test_create_session(self) -> None:
        session = create_dummy_session()

        self.session_repo.create(session)

        got_session = self.session_repo.get_session_by_session_id(session.id)

        assert got_session
        assert got_session.id == session.id
        assert got_session.status == session.status
        assert got_session.started_at == session.started_at
        assert got_session.finished_at == session.finished_at

        assert got_session.trigger
        assert got_session.trigger.type == "git.push"
        assert isinstance(got_session.trigger, CommitTrigger)
        assert isinstance(session.trigger, CommitTrigger)
        assert got_session.trigger.sha == session.trigger.sha

    def test_get_session_that_doesnt_exist(self) -> None:
        assert not self.session_repo.get_session_by_session_id(uuid4())

    def test_update_session(self) -> None:
        session = create_dummy_session()
        assert not session.finished_at

        self.session_repo.create(session)

        now = UtcDatetime.now()
        session.finished_at = now
        self.session_repo.update(session)

        updated_session = self.session_repo.get_session_by_session_id(
            session.id
        )

        assert updated_session
        assert updated_session.finished_at == now

    def test_get_recent_sessions(self) -> None:
        self.reset()

        session = create_dummy_session()
        self.session_repo.create(session)

        admin = User(uuid4(), "admin", is_admin=True)

        recents = self.session_repo.get_recent_sessions(admin)

        assert recents == [session]

    def test_get_recent_sessions_as_admin(self) -> None:
        self.reset()

        session = create_dummy_session()
        self.session_repo.create(session)

        recents = self.session_repo.get_recent_sessions_as_admin()

        assert recents == [session]

    def test_get_session_by_id_and_run_number(self) -> None:
        run_1 = create_dummy_session()
        run_2 = deepcopy(run_1)
        run_2.run = 2

        session_id = run_1.id

        self.session_repo.create(run_1)
        self.session_repo.create(run_2)

        assert (
            self.session_repo.get_session_by_session_id(session_id, 1) == run_1
        )
        assert (
            self.session_repo.get_session_by_session_id(session_id, 2) == run_2
        )
