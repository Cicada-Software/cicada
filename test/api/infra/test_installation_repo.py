from dataclasses import replace
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
        )

        installation_id = self.installation_repo.create_installation(
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

        old_id = self.installation_repo.create_installation(old_installation)
        assert old_id == old_installation.id

        new_id = self.installation_repo.create_installation(new_installation)
        assert new_id == old_id
