from unittest.mock import MagicMock

import pytest

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.application.secret.set_repository_secret import SetRepositorySecret
from cicada.domain.repository import Repository, RepositoryId
from cicada.domain.secret import Secret
from cicada.domain.user import User
from test.common import build


def test_ensure_repository_exists() -> None:
    user = build(User)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = None

    cmd = SetRepositorySecret(repository_repo, MagicMock())

    with pytest.raises(NotFound, match="Repository not found"):
        cmd.handle(user, RepositoryId(123), Secret("KEY", "VALUE"))


def test_user_has_access_to_repository() -> None:
    user = build(User)

    repository = build(Repository)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = repository
    repository_repo.can_user_access_repo.return_value = False

    cmd = SetRepositorySecret(repository_repo, MagicMock())

    msg = "You are not authorized to view this repository"

    with pytest.raises(Unauthorized, match=msg):
        cmd.handle(user, RepositoryId(123), Secret("KEY", "VALUE"))


def test_secrets_are_updated() -> None:
    user = build(User)

    repository = build(Repository, id=RepositoryId(123))

    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = repository
    repository_repo.can_user_access_repo.return_value = True

    secret_repo = MagicMock()

    cmd = SetRepositorySecret(repository_repo, secret_repo)

    secret = Secret("KEY", "VALUE")

    cmd.handle(user, repository.id, secret)

    repo_id, secrets = secret_repo.set_secrets_for_repo.call_args[0]

    assert repo_id == repository.id
    assert secrets == [secret]
