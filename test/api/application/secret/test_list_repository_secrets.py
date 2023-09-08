import re
from unittest.mock import MagicMock

import pytest

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.application.secret.list_repository_secrets import (
    ListRepositorySecrets,
)
from cicada.domain.repository import Repository, RepositoryId
from cicada.domain.user import User
from test.common import build


def test_raise_error_when_repository_is_not_found() -> None:
    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = None

    cmd = ListRepositorySecrets(repository_repo, MagicMock())

    user = build(User)

    with pytest.raises(NotFound, match="Repository not found"):
        cmd.handle(user, RepositoryId(123))


def test_raise_error_if_user_cannot_view_repo() -> None:
    repository = build(Repository)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = repository
    repository_repo.can_user_access_repo.return_value = False

    cmd = ListRepositorySecrets(repository_repo, MagicMock())

    user = build(User)

    msg = "You don't have access to this repository"

    with pytest.raises(Unauthorized, match=re.escape(msg)):
        cmd.handle(user, repository.id)


def test_keys_are_returned_if_user_has_access_to_repo() -> None:
    repository = build(Repository)

    repository_repo = MagicMock()
    repository_repo.get_repository_by_repo_id.return_value = repository
    repository_repo.can_user_access_repo.return_value = True

    secret_repo = MagicMock()
    secret_repo.list_secrets_for_repo.return_value = ["KEY"]

    cmd = ListRepositorySecrets(repository_repo, secret_repo)

    user = build(User)

    keys = cmd.handle(user, repository.id)

    assert keys == ["KEY"]
