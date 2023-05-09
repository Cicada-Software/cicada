from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

from cicada.api.domain.installation import Installation, InstallationScope
from cicada.api.domain.user import User
from cicada.api.infra.installation_repo import InstallationRepo
from cicada.api.infra.user_repo import UserRepo
from test.api.common import SqliteTestWrapper


class TestInstallationRepo(SqliteTestWrapper):
    installation_repo: InstallationRepo
    user_repo: UserRepo

    @classmethod
    def setup_class(cls) -> None:
        cls.reset()

    @classmethod
    def reset(cls) -> None:
        super().reset()

        cls.installation_repo = InstallationRepo(cls.connection)
        cls.user_repo = UserRepo(cls.connection)

    def test_create_installation(self) -> None:
        user = User(id=uuid4(), username="bob", provider="github")

        self.user_repo.create_or_update_user(user)

        installation = Installation(
            id=uuid4(),
            name="org_name",
            provider="github",
            scope=InstallationScope.ORGANIZATION,
            admin_id=user.id,
            provider_id="1337",
            provider_url="https://example.com",
        )

        installation_id = self.installation_repo.create_or_update_installation(
            installation
        )

        assert installation_id == installation.id

        installations = self.installation_repo.get_installations_for_user(user)

        assert len(installations) == 1

        assert installations[0] == installation

    def test_recreating_same_installation_retains_old_uuid(self) -> None:
        self.reset()

        user = User(id=uuid4(), username="bob", provider="github")

        self.user_repo.create_or_update_user(user)

        old_installation = Installation(
            id=uuid4(),
            name="org_name",
            provider="github",
            scope=InstallationScope.ORGANIZATION,
            admin_id=user.id,
        )

        new_installation = replace(old_installation, id=uuid4())

        old_id = self.installation_repo.create_or_update_installation(
            old_installation
        )
        assert old_id == old_installation.id

        new_id = self.installation_repo.create_or_update_installation(
            new_installation
        )
        assert new_id == old_id

    def test_get_installation_by_provider_id(self) -> None:
        self.reset()

        # TODO: make it so a user isnt required for creating an installation
        user = User(id=uuid4(), username="bob", provider="github")

        self.user_repo.create_or_update_user(user)

        installation = Installation(
            id=uuid4(),
            name="org_name",
            scope=InstallationScope.ORGANIZATION,
            admin_id=user.id,
            provider="github",
            provider_id="1337",
            provider_url="https://example.com",
        )

        self.installation_repo.create_or_update_installation(installation)

        got = self.installation_repo.get_installation_by_provider_id(
            id="1337",
            provider="github",
        )

        assert got
        assert got == installation

    def test_add_repository_to_installation(self) -> None:
        self.reset()

        user = User(id=uuid4(), username="bob", provider="github")
        self.user_repo.create_or_update_user(user)

        # TODO: use builder, the specific values here dont matter
        installation = Installation(
            id=uuid4(),
            name="org_name",
            scope=InstallationScope.ORGANIZATION,
            admin_id=user.id,
            provider="github",
            provider_id="1337",
            provider_url="https://example.com",
        )

        self.installation_repo.create_or_update_installation(installation)

        # run twice to ensure the index error doesnt occur
        for _ in range(2):
            self.installation_repo.add_repository_to_installation(
                repo=SimpleNamespace(id=1),  # type: ignore
                installation=installation,
            )

            assert self.connection

            ids = self.connection.execute(
                "SELECT repo_id FROM _installation_repos"
            ).fetchall()

            assert len(ids) == 1

            assert ids[0]["repo_id"] == 1
