import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cicada.api.di import DiContainer
from cicada.api.infra.environment_repo import EnvironmentRepo
from cicada.api.infra.gitlab.webhook_repo import GitlabWebhookRepo
from cicada.api.infra.installation_repo import InstallationRepo
from cicada.api.infra.repository_repo import RepositoryRepo
from cicada.api.infra.runner_repo import RunnerRepo
from cicada.api.infra.secret_repo_shim import SecretRepoShim
from cicada.api.infra.session_repo import SessionRepo
from cicada.api.infra.terminal_session_repo import TerminalSessionRepo
from cicada.api.infra.user_repo import UserRepo
from cicada.api.infra.waitlist_repo import WaitlistRepo
from cicada.api.middleware import cicada_exception_handler
from cicada.application.exceptions import CicadaException
from cicada.application.session.stop_session import SessionTerminator
from cicada.domain.repo.environment_repo import IEnvironmentRepo
from cicada.domain.repo.gitlab_webhook_repo import IGitlabWebhookRepo
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.runner_repo import IRunnerRepo
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.repo.user_repo import IUserRepo
from cicada.domain.repo.waitlist_repo import IWaitlistRepo
from test.api.common import SqliteTestWrapper


class TestDiContainer(SqliteTestWrapper, DiContainer):
    @classmethod
    def user_repo(cls) -> IUserRepo:
        cls._setup()

        return UserRepo(cls.connection)

    @classmethod
    def session_repo(cls) -> ISessionRepo:
        cls._setup()

        return SessionRepo(cls.connection)

    @classmethod
    def terminal_session_repo(cls) -> ITerminalSessionRepo:
        cls._setup()

        return TerminalSessionRepo(cls.connection)

    @classmethod
    def waitlist_repo(cls) -> IWaitlistRepo:
        cls._setup()

        return WaitlistRepo(cls.connection)

    @classmethod
    def repository_repo(cls) -> IRepositoryRepo:
        cls._setup()

        return RepositoryRepo(cls.connection)

    @classmethod
    def environment_repo(cls) -> IEnvironmentRepo:
        cls._setup()

        return EnvironmentRepo(cls.connection)

    @classmethod
    def installation_repo(cls) -> IInstallationRepo:
        cls._setup()

        return InstallationRepo(cls.connection)

    @classmethod
    def runner_repo(cls) -> IRunnerRepo:
        cls._setup()

        return RunnerRepo(cls.connection)

    @classmethod
    def secret_repo(cls) -> ISecretRepo:
        return SecretRepoShim()

    @classmethod
    def session_terminators(cls) -> dict[str, SessionTerminator]:
        return {}

    @classmethod
    def gitlab_webhook_repo(cls) -> IGitlabWebhookRepo:
        cls._setup()

        return GitlabWebhookRepo(cls.connection)


class TestEndpointWrapper:
    app: FastAPI
    client: TestClient
    di: TestDiContainer
    test_admin_pw: str = "password123"

    default_env: ClassVar[dict[str, str]] = {
        "CICADA_DOMAIN": "example.com",
        "GITHUB_APP_CLIENT_ID": "example_client_id",
        "GITHUB_APP_ID": "1337",
        "GITHUB_APP_CLIENT_SECRET": "secret",
        "GITHUB_APP_PRIVATE_KEY_FILE": "README.md",
        "GITHUB_WEBHOOK_SECRET": "secret",
        "GITLAB_CLIENT_ID": "id",
        "GITLAB_CLIENT_SECRET": "secret",
        "GITLAB_TOKEN_STORE_SECRET": "secret",
        "JWT_TOKEN_SECRET": "jwt secret",
        "JWT_TOKEN_EXPIRE_SECONDS": "60",
        "VAULT_ADDR": "vault_addr",
        "VAULT_TOKEN": "vault_token",
        "VAULT_USER_PASSWORD": "placeholder",
    }

    @classmethod
    def setup_class(cls) -> None:
        if not hasattr(cls, "app"):
            cls.app = FastAPI()

        with patch.dict(os.environ, {"CICADA_ADMIN_PW": cls.test_admin_pw}, clear=True):
            cls.di = TestDiContainer()
            cls.di.reset()
            cls.app.dependency_overrides[DiContainer] = lambda: cls.di

        cls.app.add_exception_handler(CicadaException, cicada_exception_handler)
        cls.client = TestClient(cls.app)

    @contextmanager
    def inject_dummy_env_vars(self) -> Iterator[dict[str, str]]:
        with patch.dict(os.environ, self.default_env, clear=True) as vars:
            yield vars
