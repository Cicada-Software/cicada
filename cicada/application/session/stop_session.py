from collections.abc import Callable, Coroutine

from cicada.application.exceptions import InvalidRequest, NotFound
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.session import Session, SessionId, SessionStatus
from cicada.domain.user import User

SessionTerminator = Callable[[Session], Coroutine[None, None, None]]


class StopSession:
    """
    Stop an active session. You can optionally supply a dictionary of key-value
    pairs, where the key is the name of the git provider, and the value is a
    callable which stops the respective session on the provider integration, if
    applicable.

    Passing a user object will require that that user have access to the
    repository which the session is running from.
    """

    def __init__(
        self,
        session_repo: ISessionRepo,
        provider_session_terminators: dict[str, SessionTerminator],
    ) -> None:
        self.session_repo = session_repo
        self.provider_session_terminators = provider_session_terminators

    async def handle(
        self, session_id: SessionId, user: User | None = None
    ) -> None:
        # TODO: test failure via user not having perms
        session = self.session_repo.get_session_by_session_id(
            session_id,
            user=user,
            permission="write",
        )

        if not session:
            raise NotFound(f"Session {session_id} not found")

        if session.finished_at:
            raise InvalidRequest("Session has already finished")

        terminator = self.provider_session_terminators.get(
            session.trigger.provider
        )

        if terminator:
            await terminator(session)

        session.finish(SessionStatus.STOPPED)
        self.session_repo.update(session)
