from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from cicada.api.common.datetime import UtcDatetime
from cicada.api.domain.repository import Repository
from cicada.api.domain.session import Session
from cicada.api.domain.triggers import CommitTrigger
from cicada.api.domain.user import User
from cicada.api.infra.repository_repo import RepositoryRepo
from cicada.api.infra.session_repo import SessionRepo
from cicada.api.infra.user_repo import UserRepo
from cicada.api.repo.repository_repo import Permission
from test.api.common import SqliteTestWrapper
from test.common import build


class TestSessionRepo(SqliteTestWrapper):
    session_repo: SessionRepo
    repository_repo: RepositoryRepo
    user_repo: UserRepo

    @classmethod
    def setup_class(cls) -> None:
        cls.reset()

    @classmethod
    def reset(cls) -> None:
        super().reset()

        cls.session_repo = SessionRepo(cls.connection)
        cls.repository_repo = RepositoryRepo(cls.connection)
        cls.user_repo = UserRepo(cls.connection)

    def test_create_session(self) -> None:
        session = build(Session)

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
        session = build(Session)

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

        session = build(Session)
        self.session_repo.create(session)

        admin = build(User, username="admin", is_admin=True)

        recents = self.session_repo.get_recent_sessions(admin)

        assert recents == [session]

    def test_get_recent_sessions_as_admin(self) -> None:
        self.reset()

        session = build(Session)
        self.session_repo.create(session)

        recents = self.session_repo.get_recent_sessions_as_admin()

        assert recents == [session]

    def test_get_session_by_id_and_run_number(self) -> None:
        run_1 = build(Session)
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

    def test_user_can_only_see_sessions_if_perms_are_valid(self) -> None:
        @dataclass
        class PermissionTest:
            required_perm: Permission
            perms: list[Permission]
            is_allowed: bool
            is_public_repo: bool = False

        tests = [
            PermissionTest(
                required_perm="read",
                perms=["read"],
                is_allowed=True,
            ),
            PermissionTest(
                required_perm="write",
                perms=["write"],
                is_allowed=True,
            ),
            PermissionTest(
                required_perm="owner",
                perms=["owner"],
                is_allowed=True,
            ),
            PermissionTest(
                required_perm="read",
                perms=["write"],
                is_allowed=True,
            ),
            PermissionTest(
                required_perm="read",
                perms=["read", "write"],
                is_allowed=True,
            ),
            PermissionTest(
                required_perm="write",
                perms=["read"],
                is_allowed=False,
            ),
            PermissionTest(
                required_perm="owner",
                perms=["write"],
                is_allowed=False,
            ),
            PermissionTest(
                required_perm="read",
                perms=[],
                is_allowed=False,
            ),
            PermissionTest(
                required_perm="read",
                perms=[],
                is_public_repo=True,
                is_allowed=True,
            ),
            PermissionTest(
                required_perm="write",
                perms=[],
                is_public_repo=True,
                is_allowed=False,
            ),
        ]

        for test in tests:
            self.reset()

            user = self.create_dummy_user(username="bob")
            session = build(Session)

            self.session_repo.create(session)

            self.create_dummy_repo_for_user(
                user,
                test.perms,
                url=session.trigger.repository_url,
                is_public=test.is_public_repo,
            )

            is_allowed = self.session_repo.can_user_access_session(
                user, session, permission=test.required_perm
            )

            assert test.is_allowed == is_allowed

    def test_get_runs_for_session2(self) -> None:
        self.reset()

        user = self.create_dummy_user(username="bob")
        session = build(Session)

        self.session_repo.create(session)

        self.create_dummy_repo_for_user(
            user,
            perms=["read"],
            url=session.trigger.repository_url,
        )

        runs = self.session_repo.get_runs_for_session2(user, session.id)

        assert len(runs) == 1
        run = runs[0]

        workflows = run.workflows[Path()]

        assert len(workflows) == 1
        workflow = workflows[0]

        assert workflow.filename == Path()
        assert workflow.sha == session.trigger.sha
        assert workflow.started_at == session.started_at
        assert workflow.finished_at == session.finished_at

    def test_get_runs_for_session2_fails_when_user_doesnt_have_access(
        self,
    ) -> None:
        self.reset()

        user = self.create_dummy_user(username="bob")
        session = build(Session)

        self.session_repo.create(session)

        self.create_dummy_repo_for_user(
            user,
            perms=[],
            url=session.trigger.repository_url,
        )

        assert not self.session_repo.get_runs_for_session2(user, session.id)

    def create_dummy_repo_for_user(
        self,
        user: User,
        perms: list[Permission],
        *,
        url: str = "example.com",
        provider: str = "github",
        is_public: bool = False,
    ) -> Repository:
        repo = self.repository_repo.update_or_create_repository(
            url=url,
            provider=provider,
            is_public=is_public,
        )

        self.repository_repo.update_user_perms_for_repo(repo, user.id, perms)

        return repo

    def create_dummy_user(self, *, username: str = "admin") -> User:
        user = build(User, username=username)

        user_id = self.user_repo.create_or_update_user(user)

        assert user_id == user.id

        return user
