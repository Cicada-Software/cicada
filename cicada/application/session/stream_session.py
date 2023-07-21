from asyncio import Queue, create_task, sleep
from collections.abc import AsyncGenerator, Callable, Coroutine

from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.session import SessionId, SessionStatus


class StreamSession:
    """
    Stream session data from multiple data sources: the terminal session which
    contains the stdout of the running program, status updates to the session,
    and the ability to stop the session mid-execution.
    """

    def __init__(
        self,
        terminal_session_repo: ITerminalSessionRepo,
        session_repo: ISessionRepo,
        stop_session: Callable[[], Coroutine[None, None, None]],
    ) -> None:
        self.terminal_session_repo = terminal_session_repo
        self.session_repo = session_repo
        self.stop_session = stop_session

        self.command_queue = Queue[str]()

    async def stream(
        self, session_id: SessionId, run: int
    ) -> AsyncGenerator[dict[str, str | list[str]], str]:
        terminal = self.terminal_session_repo.get_by_session_id(
            session_id, run
        )

        if not terminal:
            yield {"error": "Session not found"}
            return

        # TODO: dont start interceptor if session is already finished
        async def intercept_stop() -> None:
            while True:
                command = await self.command_queue.get()

                if command == "STOP":
                    await self.stop_session()
                    terminal.should_stop.set()
                    terminal.finish()

                    break

        interceptor = create_task(intercept_stop())

        async for chunks in terminal.stream_chunks():
            yield {"stdout": chunks.decode()}

        terminal.finish()

        if interceptor.done():
            yield {"status": SessionStatus.STOPPED.name}
            return

        interceptor.cancel()

        status = await self._get_session_status(session_id, run)

        yield {"status": status.name}

    async def _get_session_status(
        self, session_id: SessionId, run: int
    ) -> SessionStatus:
        """
        Repeatedly get the session to see what the new status is. Since the
        cleanup process can take a few seconds we will have to check
        periodically to until we give up (we cant wait forever, and if it gets
        stuck its probably a bug or timeout issue).
        """

        check_count = 0
        give_up_after = 10

        while check_count < give_up_after:
            session = self.session_repo.get_session_by_session_id(
                session_id, run=run
            )
            assert session

            if session.status == SessionStatus.PENDING:
                check_count += 1
                await sleep(0.5)
                continue

            return session.status

        # session is still pending, bail and return pending status
        return SessionStatus.PENDING

    def send_command(self, command: str) -> None:
        self.command_queue.put_nowait(command)
