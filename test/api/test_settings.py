import os
from unittest.mock import patch

import pytest

from cicada.api.settings import (
    DBSettings,
    GitHubSettings,
    GitlabSettings,
    JWTSettings,
    MigrationSettings,
)


class AllSettings:
    """
    A class for instantiating all env var related classes, for testing purposes
    """

    def __init__(self) -> None:
        self.jwt = JWTSettings()
        self.github = GitHubSettings()
        self.gitlab = GitlabSettings()
        self.db = DBSettings()
        self.migrate = MigrationSettings()


DEFAULT_ENV_VARS = {
    "CICADA_ADMIN_PW": "password123",
    "CICADA_DOMAIN": "example.com",
    "CICADA_PORT": "8000",
    "CICADA_HOST": "0.0.0.0",  # noqa: S104
    "DB_URL": "some_file.db3",
    "GITHUB_APP_CLIENT_ID": "client_id",
    "GITHUB_APP_CLIENT_SECRET": "client_secret",
    "GITHUB_APP_ID": "1234",
    "GITHUB_APP_PRIVATE_KEY_FILE": "README.md",
    "GITHUB_WEBHOOK_SECRET": "password123",
    "GITLAB_ACCESS_TOKEN": "password123",
    "GITLAB_WEBHOOK_SECRET": "password123",
    "JWT_TOKEN_EXPIRE_SECONDS": "123",
    "JWT_TOKEN_SECRET": "password123",
}


def test_required_vars_must_be_defined() -> None:
    non_required_env_vars = {"CICADA_HOST", "CICADA_PORT"}

    for env_var in DEFAULT_ENV_VARS:
        if env_var in non_required_env_vars:
            continue

        copy = DEFAULT_ENV_VARS.copy()
        copy.pop(env_var)

        with (
            pytest.raises(ValueError, match=f"{env_var} must be defined"),
            patch.dict(os.environ, copy, clear=True),
        ):
            AllSettings()


def test_integer_vars_must_be_integers() -> None:
    int_env_vars = {"GITHUB_APP_ID", "JWT_TOKEN_EXPIRE_SECONDS"}

    for int_env_var in int_env_vars:
        copy = DEFAULT_ENV_VARS.copy()
        copy[int_env_var] = "not an int"

        msg = f"{int_env_var} must be an integer"

        with (
            pytest.raises(ValueError, match=msg),
            patch.dict(os.environ, copy, clear=True),
        ):
            AllSettings()


def test_github_key_file_must_be_valid_filename() -> None:
    for filename in ("", ".", "/tmp"):  # noqa: S108
        copy = DEFAULT_ENV_VARS.copy()
        copy["GITHUB_APP_PRIVATE_KEY_FILE"] = filename

        msg = "must be defined, or file doesn't exist"

        with (
            pytest.raises(ValueError, match=msg),
            patch.dict(os.environ, copy, clear=True),
        ):
            AllSettings()
