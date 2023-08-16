import os
from contextlib import suppress
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

from cicada.domain.triggers import Trigger, json_to_trigger

with suppress(ModuleNotFoundError):
    from dotenv import load_dotenv

    load_dotenv()


# TODO: use descriptors for env var magic


def trigger_from_env(override: str = "") -> Trigger | None:
    env = override or os.getenv("CICADA_TRIGGER", "")

    return json_to_trigger(env) if env else None


class MigrationSettings:
    default_admin_password: str

    def __init__(self) -> None:
        self.default_admin_password = os.getenv("CICADA_ADMIN_PW", "")

        if not self.default_admin_password:
            raise ValueError("CICADA_ADMIN_PW must be defined")


class DBSettings:
    db_url: str

    def __init__(self) -> None:
        self.db_url = os.getenv("DB_URL", "")

        if not self.db_url:
            raise ValueError("DB_URL must be defined")


class ExecutionSettings:
    executor: str

    # TODO: make this dynamic
    AVAILABLE_EXECUTORS: ClassVar[set[str]] = {
        "remote-podman",
        "remote-docker",
    }

    def __init__(self) -> None:
        self.executor = os.getenv("CICADA_EXECUTOR", "remote-podman")

        if self.executor not in self.AVAILABLE_EXECUTORS:
            executors = ", ".join(f'"{x}"' for x in self.AVAILABLE_EXECUTORS)

            raise ValueError(f"CICADA_EXECUTOR must be one of: {executors}")


class DNSSettings:
    domain: str
    host: str
    port: int

    def __init__(self) -> None:
        self.domain = os.getenv("CICADA_DOMAIN", "")

        if not self.domain:
            raise ValueError("CICADA_DOMAIN must be defined")

        if not self.is_domain_only_url(self.domain):
            domain = self.format_invalid_domain_url(self.domain)

            raise ValueError(
                f'CICADA_DOMAIN must be domain only. Did you mean "{domain}"?'
            )

        if self.domain.startswith("www."):
            raise ValueError(
                f'CICADA_DOMAIN should not include "www" sub-domains. Did you mean "{self.domain[4:]}"?'  # noqa: E501
            )

        self.host = os.getenv("CICADA_HOST", "0.0.0.0")  # noqa: S104

        if not self.host:
            raise ValueError("CICADA_HOST must be defined")

        try:
            self.port = int(os.getenv("CICADA_PORT", "8000"))

        except ValueError as ex:
            raise ValueError("CICADA_PORT must be an integer") from ex

        if not self.port:
            raise ValueError("CICADA_PORT must be defined")

    def is_domain_only_url(self, url: str) -> bool:
        # A domain is considered valid if it is only the domain part of a URL,
        # that is, it does not contain a schema, path, query params, etc. This
        # could be handled more elegantly (and could also be re-written as a
        # regex), but this works for now.

        p = urlparse(url)

        return not (
            any((p.scheme, p.netloc, p.params, p.query, p.fragment))
            or "/" in p.path
        )

    def format_invalid_domain_url(self, url: str) -> str:
        p = urlparse(url)

        return p.netloc if p.netloc else p.path.split("/")[0]


class GitProviderSettings(DNSSettings):
    repo_white_list: list[str]
    enabled_providers: set[str]

    AVAILABLE_PROVIDERS: ClassVar[set[str]] = {"github", "gitlab"}

    def __init__(self) -> None:
        super().__init__()

        self.repo_white_list = os.getenv("REPO_WHITE_LIST", "").split(",")

        if not self.repo_white_list:
            raise ValueError(
                "GITHUB_REPO_WHITE_LIST is empty, no workflows will be allowed"
            )

        self.enabled_providers = {
            stripped
            for provider in os.getenv(
                "ENABLED_PROVIDERS", "github,gitlab"
            ).split(",")
            if (stripped := provider.strip())
        }

        if self.enabled_providers - self.AVAILABLE_PROVIDERS:
            providers = ", ".join(f'"{x}"' for x in self.AVAILABLE_PROVIDERS)

            raise ValueError(f"ENABLED_PROVIDERS can only contain {providers}")


class GitlabSettings(GitProviderSettings):
    access_token: str
    webhook_secret: str

    def __init__(self) -> None:
        super().__init__()

        self.access_token = os.getenv("GITLAB_ACCESS_TOKEN", "")

        if not self.access_token:
            raise ValueError("GITLAB_ACCESS_TOKEN must be defined")

        self.webhook_secret = os.getenv("GITLAB_WEBHOOK_SECRET", "")

        if not self.webhook_secret:
            raise ValueError("GITLAB_WEBHOOK_SECRET must be defined")


class GitHubSettings(GitProviderSettings):
    app_id: int
    client_id: str
    client_secret: str
    key_file: Path
    sso_redirect_uri: str
    webhook_secret: str

    def __init__(self) -> None:
        super().__init__()

        try:
            self.app_id = int(os.getenv("GITHUB_APP_ID", "0"))

        except ValueError as ex:
            raise ValueError("GITHUB_APP_ID must be an integer") from ex

        if not self.app_id:
            raise ValueError("GITHUB_APP_ID must be defined")

        self.client_id = os.getenv("GITHUB_APP_CLIENT_ID", "")

        if not self.client_id:
            raise ValueError("GITHUB_APP_CLIENT_ID must be defined")

        self.client_secret = os.getenv("GITHUB_APP_CLIENT_SECRET", "")

        if not self.client_secret:
            raise ValueError("GITHUB_APP_CLIENT_SECRET must be defined")

        self.key_file = Path(os.getenv("GITHUB_APP_PRIVATE_KEY_FILE", ""))

        if not (self.key_file.exists() and self.key_file.is_file()):
            raise ValueError(
                "GITHUB_APP_PRIVATE_KEY_FILE must be defined, or file doesn't exist"  # noqa: E501
            )

        self.webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")

        if not self.webhook_secret:
            raise ValueError("GITHUB_WEBHOOK_SECRET must be defined")

        self.sso_redirect_uri = f"https://{self.domain}/api/github_sso"


Seconds = int


class JWTSettings(DNSSettings):
    secret: str
    expiration_timeout: Seconds

    def __init__(self) -> None:
        super().__init__()

        self.secret = os.getenv("JWT_TOKEN_SECRET", "")

        if not self.secret:
            raise ValueError("JWT_TOKEN_SECRET must be defined")

        try:
            self.expiration_timeout = int(
                os.getenv("JWT_TOKEN_EXPIRE_SECONDS", "0")
            )

        except ValueError as ex:
            raise ValueError(
                "JWT_TOKEN_EXPIRE_SECONDS must be an integer"
            ) from ex

        if not self.expiration_timeout:
            raise ValueError("JWT_TOKEN_EXPIRE_SECONDS must be defined")


# TODO: rename
class NotificationSettings:
    url: str
    is_enabled: bool

    def __init__(self) -> None:
        self.url = os.getenv("NTFY_NOTIFICATION_URL", "")

        self.is_enabled = bool(self.url)


class SMTPSettings:
    domain: str
    username: str
    password: str

    def __init__(self) -> None:
        self.domain = os.getenv("SMTP_DOMAIN", "")
        if not self.domain:
            raise ValueError("SMTP_DOMAIN must be set")

        self.username = os.getenv("SMTP_USERNAME", "")
        if not self.username:
            raise ValueError("SMTP_USERNAME must be set")

        self.password = os.getenv("SMTP_PASSWORD", "")
        if not self.password:
            raise ValueError("SMTP_PASSWORD must be set")


def verify_env_vars() -> None:
    """
    Eagerly load env vars to see if they are valid. The env vars are only valid
    at the time this function is called: if the env vars change, they may be
    reloaded and potentially invalid.
    """

    DBSettings()
    ExecutionSettings()
    GitHubSettings()
    GitlabSettings()
    JWTSettings()
    MigrationSettings()
    NotificationSettings()
