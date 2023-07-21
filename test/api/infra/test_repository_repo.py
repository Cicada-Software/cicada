from cicada.api.infra.repository_repo import RepositoryRepo
from cicada.domain.repository import Repository
from cicada.domain.user import User
from test.api.common import SqliteTestWrapper
from test.common import build


class TestRepositoryRepo(SqliteTestWrapper):
    repo: RepositoryRepo

    @classmethod
    def setup_class(cls) -> None:
        cls.reset()

    @classmethod
    def reset(cls) -> None:
        super().reset()

        cls.repo = RepositoryRepo(cls.connection)

    def test_create_repository(self) -> None:
        repo = self.repo.update_or_create_repository(
            url="https://github.com/user/repo",
            provider="github",
            is_public=False,
        )

        assert repo.id
        assert repo.provider == "github"
        assert repo.url == "https://github.com/user/repo"
        assert not repo.is_public

        # Test inserting same repository does nothing
        repo2 = self.repo.update_or_create_repository(
            url="https://github.com/user/repo",
            provider="github",
            is_public=False,
        )

        assert repo == repo2

    def test_create_public_repository(self) -> None:
        self.reset()

        repo = self.repo.update_or_create_repository(
            url="https://github.com/user/repo",
            provider="github",
            is_public=True,
        )

        assert repo.id
        assert repo.provider == "github"
        assert repo.url == "https://github.com/user/repo"
        assert repo.is_public

    def test_any_user_has_read_access_to_public_repo(self) -> None:
        user = build(User)

        repo = self.repo.update_or_create_repository(
            url="example.com",
            provider="github",
            is_public=True,
        )

        assert self.repo.can_user_access_repo(user, repo, permission="read")
        assert not self.repo.can_user_access_repo(
            user, repo, permission="write"
        )
        assert not self.repo.can_user_access_repo(
            user, repo, permission="owner"
        )

    def test_user_cannot_access_nonexistent_repo(self) -> None:
        user = build(User)
        repo = build(Repository, id=1337)

        assert not self.repo.can_user_access_repo(
            user, repo, permission="read"
        )
        assert not self.repo.can_user_access_repo(
            user, repo, permission="write"
        )
        assert not self.repo.can_user_access_repo(
            user, repo, permission="owner"
        )
