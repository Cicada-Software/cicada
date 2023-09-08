from unittest.mock import MagicMock

from cicada.application.secret.gather_secrets_from_trigger import (
    GatherSecretsFromTrigger,
)
from cicada.domain.repository import Repository
from cicada.domain.secret import Secret
from cicada.domain.triggers import CommitTrigger
from test.common import build


def test_no_data_returned_if_repository_doesnt_exist() -> None:
    trigger = build(CommitTrigger)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_url_and_provider.return_value = None

    cmd = GatherSecretsFromTrigger(repository_repo, MagicMock(), MagicMock())

    secrets = cmd.handle(trigger)

    assert not secrets


def test_pull_repository_and_installation_secrets() -> None:
    trigger = build(CommitTrigger)

    repository = build(Repository)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_url_and_provider.return_value = (
        repository
    )

    secret_repo = MagicMock()
    secret_repo.get_secrets_for_installation.return_value = [
        Secret("INSTALLATION", "installation secret"),
    ]
    secret_repo.get_secrets_for_repo.return_value = [
        Secret("REPOSITORY", "repository secret"),
    ]

    cmd = GatherSecretsFromTrigger(repository_repo, MagicMock(), secret_repo)

    secrets = cmd.handle(trigger)

    assert secrets == {
        "INSTALLATION": "installation secret",
        "REPOSITORY": "repository secret",
    }


def test_repository_secrets_override_installation_secrets() -> None:
    trigger = build(CommitTrigger)

    repository = build(Repository)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_url_and_provider.return_value = (
        repository
    )

    secret_repo = MagicMock()
    secret_repo.get_secrets_for_installation.return_value = [
        Secret("KEY", "installation"),
    ]
    secret_repo.get_secrets_for_repo.return_value = [
        Secret("KEY", "repository"),
    ]

    cmd = GatherSecretsFromTrigger(repository_repo, MagicMock(), secret_repo)

    secrets = cmd.handle(trigger)

    assert secrets == {"KEY": "repository"}
