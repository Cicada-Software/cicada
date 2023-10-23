from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.application.secret.delete_installation_secret import DeleteInstallationSecret
from cicada.domain.installation import Installation
from cicada.domain.user import User
from test.common import build


def test_installation_must_exist() -> None:
    user = build(User)

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = []

    cmd = DeleteInstallationSecret(installation_repo, MagicMock())

    with pytest.raises(NotFound, match="Installation not found"):
        cmd.handle(user, uuid4(), "SOME_KEY")


def test_user_must_be_admin() -> None:
    user = build(User)

    installation = build(Installation)

    assert installation.admin_id != user.id

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = [installation]

    cmd = DeleteInstallationSecret(installation_repo, MagicMock())

    msg = "You do not have access to this installation"

    with pytest.raises(Unauthorized, match=msg):
        cmd.handle(user, installation.id, "SOME_KEY")


def test_key_is_deleted_if_user_is_authorized_to_do_so() -> None:
    user = build(User)

    installation = build(Installation, admin_id=user.id)

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = [installation]

    secret_repo = MagicMock()

    cmd = DeleteInstallationSecret(installation_repo, secret_repo)

    cmd.handle(user, installation.id, "SOME_KEY")

    id, key = secret_repo.delete_installation_secret.call_args[0]

    assert id == installation.id
    assert key == "SOME_KEY"
