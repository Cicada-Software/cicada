import os
import re
from unittest.mock import patch

import pytest

from cicada.api.settings import (
    DBSettings,
    DNSSettings,
    ExecutionSettings,
    GitHubSettings,
    GitlabSettings,
    GitProviderSettings,
    JWTSettings,
    MigrationSettings,
    NotificationSettings,
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


def test_enabled_providers_must_be_valid() -> None:
    is_provider_list_valid = {
        "github": True,
        "gitlab": True,
        "gitlab,github": True,
        "gitlab, github": True,
        " gitlab, github ": True,
        "": True,
        "xyz": False,
        "github,xyz": False,
        "github,gitlab,xyz": False,
    }

    for providers, is_valid in is_provider_list_valid.items():
        copy = {**DEFAULT_ENV_VARS, "ENABLED_PROVIDERS": providers}

        with patch.dict(os.environ, copy, clear=True):
            if is_valid:
                GitProviderSettings()

            else:
                with pytest.raises(ValueError, match="can only contain"):
                    GitProviderSettings()


def test_executor_must_be_valid() -> None:
    is_executor_valid = {
        "docker": False,
        "podman": False,
        "": False,
        "xyz": False,
    }

    for executor, is_valid in is_executor_valid.items():
        copy = {**DEFAULT_ENV_VARS, "CICADA_EXECUTOR": executor}

        with patch.dict(os.environ, copy, clear=True):
            if is_valid:
                ExecutionSettings()

            else:
                with pytest.raises(ValueError, match="must be one of"):
                    ExecutionSettings()


def test_notification_settings() -> None:
    should_be_enabled = {
        "some url": True,
        "": False,
        None: False,
    }

    for url, enabled in should_be_enabled.items():
        env_vars = DEFAULT_ENV_VARS.copy()

        if url is not None:
            env_vars["NTFY_NOTIFICATION_URL"] = url

        with patch.dict(os.environ, env_vars, clear=True):
            settings = NotificationSettings()

            assert settings.url == (url or "")
            assert settings.is_enabled == enabled


def test_dns_settings_cannot_be_empty() -> None:
    for env_var in ("CICADA_DOMAIN", "CICADA_HOST"):
        copy = {**DEFAULT_ENV_VARS, env_var: ""}

        with (
            pytest.raises(ValueError, match=f"{env_var} must be defined"),
            patch.dict(os.environ, copy, clear=True),
        ):
            DNSSettings()


def test_dns_settings_port_must_be_int() -> None:
    tests = ("asdf", "3.14")

    for port in tests:
        copy = {**DEFAULT_ENV_VARS, "CICADA_PORT": port}

        with (
            pytest.raises(ValueError, match="CICADA_PORT must be an integer"),
            patch.dict(os.environ, copy, clear=True),
        ):
            DNSSettings()


def test_validate_dns_settings() -> None:
    tests = {
        "https://example.com": re.escape('Did you mean "example.com"?'),
        "example.com/": re.escape('Did you mean "example.com"?'),
        "example.com/api": re.escape('Did you mean "example.com"?'),
        "example.com?test=1": re.escape('Did you mean "example.com"?'),
        "www.example.com": 'should not include "www" .* Did you mean "example.com"',
    }

    for url, error in tests.items():
        copy = {**DEFAULT_ENV_VARS, "CICADA_DOMAIN": url}

        with (
            pytest.raises(ValueError, match=error),
            patch.dict(os.environ, copy, clear=True),
        ):
            DNSSettings()
