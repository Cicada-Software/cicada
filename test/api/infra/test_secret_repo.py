import os
from uuid import uuid4

import pytest

from cicada.api.infra.secret_repo import SecretRepo
from cicada.domain.repository import RepositoryId
from cicada.domain.secret import Secret
from test.api.common import SqliteTestWrapper


@pytest.mark.skipif(not os.getenv("VAULT_ADDR"), reason="Vault is not setup")
class TestSecretRepo(SqliteTestWrapper):
    repo: SecretRepo

    @classmethod
    def setup_class(cls) -> None:
        cls.reset()

    @classmethod
    def reset(cls) -> None:
        super().reset()

        cls.repo = SecretRepo(cls.connection)

    def test_nothing_is_returned_when_no_seecrets_are_added(self) -> None:
        assert not self.repo.get_secrets_for_repo(RepositoryId(123))

        assert not self.repo.get_secrets_for_installation(uuid4())

    def test_set_and_get_secrets_for_repo(self) -> None:
        self.reset()

        id = RepositoryId(123)

        secret_a = Secret("A", "1")
        secret_b = Secret("B", "1")

        self.repo.set_secrets_for_repo(id, [secret_a, secret_b])

        secrets = self.repo.get_secrets_for_repo(id)

        assert len(secrets) == 2

        # TODO: ensure secrets are returned in order of insertion
        secrets = sorted(secrets, key=lambda x: x.key)

        assert secrets == [secret_a, secret_b]

    def test_set_and_get_secrets_for_installation(self) -> None:
        self.reset()

        id = uuid4()

        secret_a = Secret("A", "1")
        secret_b = Secret("B", "1")

        self.repo.set_secrets_for_installation(id, [secret_a, secret_b])

        secrets = self.repo.get_secrets_for_installation(id)

        assert len(secrets) == 2

        # TODO: ensure secrets are returned in order of insertion
        secrets = sorted(secrets, key=lambda x: x.key)

        assert secrets == [secret_a, secret_b]

    def test_update_existing_repository_secret(self) -> None:
        self.reset()

        id = RepositoryId(123)

        secret = Secret("A", "1")

        self.repo.set_secrets_for_repo(id, [secret])
        secrets = self.repo.get_secrets_for_repo(id)

        assert secrets == [secret]

        new_secret = Secret("A", "2")

        self.repo.set_secrets_for_repo(id, [new_secret])
        secrets = self.repo.get_secrets_for_repo(id)

        assert secrets == [new_secret]

        assert new_secret.updated_at > secret.updated_at

    def test_update_existing_installation_secret(self) -> None:
        self.reset()

        id = uuid4()

        secret = Secret("A", "1")

        self.repo.set_secrets_for_installation(id, [secret])
        secrets = self.repo.get_secrets_for_installation(id)

        assert secrets == [secret]

        new_secret = Secret("A", "2")

        self.repo.set_secrets_for_installation(id, [new_secret])
        secrets = self.repo.get_secrets_for_installation(id)

        assert secrets == [new_secret]

        assert new_secret.updated_at > secret.updated_at
