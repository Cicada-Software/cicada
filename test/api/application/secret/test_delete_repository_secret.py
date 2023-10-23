from unittest.mock import MagicMock

import pytest

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.application.secret.delete_repository_secret import DeleteRepositorySecret
from cicada.domain.repository import Repository, RepositoryId
from cicada.domain.user import User
from test.common import build


def test_repository_must_exist() -> None:
    user = build(User)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = None

    cmd = DeleteRepositorySecret(repository_repo, MagicMock())

    with pytest.raises(NotFound, match="Repository not found"):
        cmd.handle(user, RepositoryId(123), "SOME_KEY")


def test_user_must_be_admin() -> None:
    user = build(User)

    repository = build(Repository)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = repository
    repository_repo.can_user_access_repo.return_value = False

    cmd = DeleteRepositorySecret(repository_repo, MagicMock())

    msg = "You are not allowed to delete repository secrets"

    with pytest.raises(Unauthorized, match=msg):
        cmd.handle(user, repository.id, "SOME_KEY")


def test_key_is_deleted_if_user_is_authorized_to_do_so() -> None:
    user = build(User)

    repository = build(Repository)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = repository
    repository_repo.can_user_access_repo.return_value = True

    secret_repo = MagicMock()

    cmd = DeleteRepositorySecret(repository_repo, secret_repo)

    cmd.handle(user, repository.id, "SOME_KEY")

    id, key = secret_repo.delete_repository_secret.call_args[0]

    assert id == repository.id
    assert key == "SOME_KEY"
