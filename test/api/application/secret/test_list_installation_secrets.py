import re
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cicada.application.exceptions import NotFound, Unauthorized
from cicada.application.secret.list_installation_secrets import (
    ListInstallationSecrets,
)
from cicada.domain.installation import Installation
from cicada.domain.user import User
from test.common import build


def test_raise_error_if_user_cannot_view_installation() -> None:
    user = build(User)

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = []

    cmd = ListInstallationSecrets(installation_repo, MagicMock())

    with pytest.raises(NotFound, match="Installation not found"):
        cmd.handle(user, uuid4())


def test_user_must_be_admin_to_view_secrets_for_installation() -> None:
    user = build(User)

    installation = build(Installation)

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = [installation]

    assert installation.admin_id != user.id

    cmd = ListInstallationSecrets(installation_repo, MagicMock())

    msg = "You are not authorized to this installation"

    with pytest.raises(Unauthorized, match=re.escape(msg)):
        cmd.handle(user, installation.id)


def test_admin_user_cannot_access_other_installations() -> None:
    user = build(User)

    installation = build(Installation)

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = [installation]

    assert installation.admin_id != user.id

    cmd = ListInstallationSecrets(installation_repo, MagicMock())

    with pytest.raises(NotFound, match="Installation not found"):
        cmd.handle(user, uuid4())


def test_secret_keys_returned_if_user_can_access_installation() -> None:
    user = build(User)

    installation = build(Installation, admin_id=user.id)

    installation_repo = MagicMock()
    installation_repo.get_installations_for_user.return_value = [installation]

    secret_repo = MagicMock()
    secret_repo.list_secrets_for_installation.return_value = ["KEY"]

    cmd = ListInstallationSecrets(installation_repo, secret_repo)

    keys = cmd.handle(user, installation.id)

    assert keys == ["KEY"]
