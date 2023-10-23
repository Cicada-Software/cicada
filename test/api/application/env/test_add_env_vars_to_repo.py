from unittest.mock import MagicMock

import pytest

from cicada.application.env.add_env_vars_to_repo import AddEnvironmentVariablesToRepository
from cicada.application.exceptions import NotFound, Unauthorized
from cicada.domain.env_var import EnvironmentVariable
from cicada.domain.repository import Repository
from cicada.domain.user import User
from test.common import build


def test_user_not_found_throws_error() -> None:
    user_repo = MagicMock()
    repository_repo = MagicMock()
    env_repo = MagicMock()

    user_repo.get_user_by_username.return_value = None

    cmd = AddEnvironmentVariablesToRepository(
        user_repo=user_repo,
        repository_repo=repository_repo,
        env_repo=env_repo,
    )

    with pytest.raises(NotFound, match="User not found"):
        cmd.handle(
            username="bob",
            repo_url="anything",
            provider="anything",
            env_vars=[EnvironmentVariable("HELLO", "world")],
        )

    user_repo.get_user_by_username.assert_called_once_with("bob")
    repository_repo.get_repository_by_url_and_provider.assert_not_called()
    repository_repo.can_user_access_repo.assert_not_called()
    env_repo.set_env_vars_for_repo.assert_not_called()


def test_repo_not_found_raises_error() -> None:
    user_repo = MagicMock()
    repository_repo = MagicMock()
    env_repo = MagicMock()

    user_repo.get_user_by_username.return_value = build(User, username="bob")
    repository_repo.get_repository_by_url_and_provider.return_value = None

    cmd = AddEnvironmentVariablesToRepository(
        user_repo=user_repo,
        repository_repo=repository_repo,
        env_repo=env_repo,
    )

    with pytest.raises(NotFound, match="Repository .* not found"):
        cmd.handle(
            username="bob",
            repo_url="anything",
            provider="anything",
            env_vars=[EnvironmentVariable("HELLO", "world")],
        )

    user_repo.get_user_by_username.assert_called_once_with("bob")
    repository_repo.get_repository_by_url_and_provider.assert_called_once()
    repository_repo.can_user_access_repo.assert_not_called()
    env_repo.set_env_vars_for_repo.assert_not_called()


def test_adding_env_var_works() -> None:
    user_repo = MagicMock()
    repository_repo = MagicMock()
    env_repo = MagicMock()

    user = build(User, username="bob")
    user_repo.get_user_by_username.return_value = user

    repo = Repository(id=1, url="http://example.com", provider="example")
    repository_repo.get_repository_by_url_and_provider.return_value = repo

    cmd = AddEnvironmentVariablesToRepository(
        user_repo=user_repo,
        repository_repo=repository_repo,
        env_repo=env_repo,
    )

    env_var = EnvironmentVariable("HELLO", "world")

    cmd.handle(
        username="bob",
        repo_url=repo.url,
        provider=repo.provider,
        env_vars=[env_var],
    )

    user_repo.get_user_by_username.assert_called_once_with("bob")
    repository_repo.get_repository_by_url_and_provider.assert_called_once_with(
        repo.url, repo.provider
    )
    repository_repo.can_user_access_repo.assert_called_once_with(user, repo)
    env_repo.set_env_vars_for_repo.assert_called_once_with(repo.id, [env_var])


def test_user_who_cannot_see_repo_is_denied() -> None:
    user_repo = MagicMock()
    repository_repo = MagicMock()
    env_repo = MagicMock()

    user = build(User, username="bob")
    user_repo.get_user_by_username.return_value = user

    repo = Repository(id=1, url="http://example.com", provider="example")
    repository_repo.get_repository_by_url_and_provider.return_value = repo

    repository_repo.can_user_access_repo.return_value = False

    cmd = AddEnvironmentVariablesToRepository(
        user_repo=user_repo,
        repository_repo=repository_repo,
        env_repo=env_repo,
    )

    env_var = EnvironmentVariable("HELLO", "world")

    msg = "User is not allowed to modify env vars"

    with pytest.raises(Unauthorized, match=msg):
        cmd.handle(
            username="bob",
            repo_url=repo.url,
            provider=repo.provider,
            env_vars=[env_var],
        )

    user_repo.get_user_by_username.assert_called_once_with("bob")
    repository_repo.get_repository_by_url_and_provider.assert_called_once_with(
        repo.url, repo.provider
    )
    repository_repo.can_user_access_repo.assert_called_once_with(user, repo)
    env_repo.set_env_vars_for_repo.assert_not_called()
