from cicada.api.application.session.stop_session import SessionTerminator
from cicada.api.infra.environment_repo import EnvironmentRepo
from cicada.api.infra.github.stop_session import github_session_terminator
from cicada.api.infra.repository_repo import RepositoryRepo
from cicada.api.infra.session_repo import SessionRepo
from cicada.api.infra.terminal_session_repo import TerminalSessionRepo
from cicada.api.infra.user_repo import UserRepo
from cicada.api.infra.waitlist_repo import WaitlistRepo
from cicada.api.repo.environment_repo import IEnvironmentRepo
from cicada.api.repo.repository_repo import IRepositoryRepo
from cicada.api.repo.session_repo import ISessionRepo
from cicada.api.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.api.repo.user_repo import IUserRepo
from cicada.api.repo.waitlist_repo import IWaitlistRepo


class DiContainer:  # pragma: no cover
    # TODO: move settings classes here so they can be injected without patching

    @classmethod
    def user_repo(cls) -> IUserRepo:
        return UserRepo()

    @classmethod
    def session_repo(cls) -> ISessionRepo:
        return SessionRepo()

    @classmethod
    def terminal_session_repo(cls) -> ITerminalSessionRepo:
        return TerminalSessionRepo()

    @classmethod
    def waitlist_repo(cls) -> IWaitlistRepo:
        return WaitlistRepo()

    @classmethod
    def repository_repo(cls) -> IRepositoryRepo:
        return RepositoryRepo()

    @classmethod
    def environment_repo(cls) -> IEnvironmentRepo:
        return EnvironmentRepo()

    @classmethod
    def session_terminators(cls) -> dict[str, SessionTerminator]:
        return {"github": github_session_terminator}
