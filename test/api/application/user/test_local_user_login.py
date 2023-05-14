from unittest.mock import MagicMock

import pytest

from cicada.api.application.exceptions import Unauthorized
from cicada.api.application.user.local_user_login import LocalUserLogin
from cicada.api.common.password_hash import PasswordHash
from cicada.api.domain.user import User
from test.common import build


def test_login_as_unknown_user_fails() -> None:
    user_repo = MagicMock()

    user_repo.get_user_by_username.return_value = None

    cmd = LocalUserLogin(user_repo)

    with pytest.raises(Unauthorized):
        cmd.handle("any username", "any password")


def test_non_local_user_login_fails() -> None:
    user_repo = MagicMock()

    sso_user = build(User, username="bob")

    user_repo.get_user_by_username.return_value = sso_user

    cmd = LocalUserLogin(user_repo)

    with pytest.raises(Unauthorized):
        cmd.handle("bob", "any password")


def test_incorrect_password_fails() -> None:
    user_repo = MagicMock()

    user = build(
        User,
        username="bob",
        password_hash=PasswordHash.from_password("123456"),
    )

    user_repo.get_user_by_username.return_value = user

    cmd = LocalUserLogin(user_repo)

    with pytest.raises(Unauthorized):
        cmd.handle(user.username, "invalid password")


def test_login_with_correct_password_works() -> None:
    user_repo = MagicMock()

    password = "password123"  # noqa: S105

    user = build(
        User,
        username="bob",
        password_hash=PasswordHash.from_password(password),
    )

    user_repo.get_user_by_username.return_value = user

    cmd = LocalUserLogin(user_repo)

    got_user = cmd.handle(user.username, password)

    assert got_user == user
