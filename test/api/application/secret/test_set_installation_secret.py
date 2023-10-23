from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.application.secret.set_installation_secret import SetInstallationSecret
from cicada.domain.installation import Installation
from cicada.domain.secret import Secret
from cicada.domain.user import User
from test.common import build


def test_ensure_installation_exists() -> None:
    user = build(User)

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = []

    cmd = SetInstallationSecret(installation_repo, MagicMock())

    with pytest.raises(NotFound, match="Installation not found"):
        cmd.handle(user, uuid4(), Secret("KEY", "VALUE"))


def test_ensure_user_must_have_admin_access_on_installation() -> None:
    user = build(User)

    installation = build(Installation)

    assert installation.admin_id != user.id

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = [installation]

    cmd = SetInstallationSecret(installation_repo, MagicMock())

    msg = "You do not have access to this installation"

    with pytest.raises(Unauthorized, match=msg):
        cmd.handle(user, installation.id, Secret("KEY", "VALUE"))


def test_secrets_are_updated_if_user_has_proper_access() -> None:
    user = build(User)

    installation = build(Installation, admin_id=user.id)

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = [installation]

    secret_repo = MagicMock()

    cmd = SetInstallationSecret(installation_repo, secret_repo)

    secret = Secret("KEY", "VALUE")

    cmd.handle(user, installation.id, secret)

    (
        installation_id,
        secrets,
    ) = secret_repo.set_secrets_for_installation.call_args[0]

    assert installation_id == installation.id
    assert secrets == [secret]
