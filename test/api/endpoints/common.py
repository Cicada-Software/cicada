import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cicada.api.application.exceptions import CicadaException
from cicada.api.application.session.stop_session import SessionTerminator
from cicada.api.di import DiContainer
from cicada.api.infra.environment_repo import EnvironmentRepo
from cicada.api.infra.installation_repo import InstallationRepo
from cicada.api.infra.repository_repo import RepositoryRepo
from cicada.api.infra.session_repo import SessionRepo
from cicada.api.infra.terminal_session_repo import TerminalSessionRepo
from cicada.api.infra.user_repo import UserRepo
from cicada.api.infra.waitlist_repo import WaitlistRepo
from cicada.api.middleware import cicada_exception_handler
from cicada.api.repo.environment_repo import IEnvironmentRepo
from cicada.api.repo.installation_repo import IInstallationRepo
from cicada.api.repo.repository_repo import IRepositoryRepo
from cicada.api.repo.session_repo import ISessionRepo
from cicada.api.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.api.repo.user_repo import IUserRepo
from cicada.api.repo.waitlist_repo import IWaitlistRepo
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
    def session_terminators(cls) -> dict[str, SessionTerminator]:
        return {}


class TestEndpointWrapper:
    app: FastAPI
    client: TestClient
    di: TestDiContainer
    test_admin_pw: str = "password123"

    default_env: Final = {
        "CICADA_DOMAIN": "example.com",
        "GITHUB_APP_CLIENT_ID": "example_client_id",
        "GITHUB_APP_ID": "1337",
        "GITHUB_APP_CLIENT_SECRET": "secret",
        "GITHUB_APP_PRIVATE_KEY_FILE": "README.md",
        "GITHUB_WEBHOOK_SECRET": "secret",
        "GITLAB_WEBHOOK_SECRET": "secret",
        "GITLAB_ACCESS_TOKEN": "access-token",
        "JWT_TOKEN_SECRET": "jwt secret",
        "JWT_TOKEN_EXPIRE_SECONDS": "60",
    }

    @classmethod
    def setup_class(cls) -> None:
        if not hasattr(cls, "app"):
            cls.app = FastAPI()

        with patch.dict(
            os.environ, {"CICADA_ADMIN_PW": cls.test_admin_pw}, clear=True
        ):
            cls.di = TestDiContainer()
            cls.di.reset()
            cls.app.dependency_overrides[DiContainer] = lambda: cls.di

        cls.app.add_exception_handler(
            CicadaException, cicada_exception_handler
        )
        cls.client = TestClient(cls.app)

    @contextmanager
    def inject_dummy_env_vars(self) -> Iterator[dict[str, str]]:
        with patch.dict(os.environ, self.default_env, clear=True) as vars:
            yield vars
