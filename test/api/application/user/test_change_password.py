from unittest.mock import MagicMock

import pytest

from cicada.application.exceptions import Unauthorized
from cicada.application.user.change_password import ChangePassword
from cicada.domain.user import User
from test.common import build


def test_user_user_password_is_updated_when_changing_password() -> None:
    user_repo = MagicMock()

    cmd = ChangePassword(user_repo)

    user = build(User, username="bob", provider="cicada")

    new_password = "password123"  # noqa: S105

    cmd.handle(user, new_password)

    user_repo.create_or_update_user.assert_called_once_with(user)

    # TODO: dont modify passed in user object, return new one
    assert user.password_hash
    assert user.password_hash.verify(new_password)


def test_non_local_user_cannot_change_password() -> None:
    user_repo = MagicMock()
    cmd = ChangePassword(user_repo)

    user = build(User, username="bob", provider="github")

    msg = "Only local users can change their password"

    with pytest.raises(Unauthorized, match=msg):
        cmd.handle(user, "password123")

    assert not user.password_hash

    user_repo.create_or_update_user.assert_not_called()
