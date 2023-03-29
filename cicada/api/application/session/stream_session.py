from asyncio import Queue, create_task, sleep
from collections.abc import AsyncGenerator, Callable, Coroutine
from uuid import UUID

from cicada.api.domain.session import SessionStatus
from cicada.api.repo.session_repo import ISessionRepo
from cicada.api.repo.terminal_session_repo import ITerminalSessionRepo


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
        self, session_id: UUID, run: int
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
                    terminal.should_stop.set()  # type: ignore
                    terminal.finish()  # type: ignore

                    break

        interceptor = create_task(intercept_stop())

        async for lines in terminal.stream_batched_lines():
            yield {"stdout": lines}

        terminal.finish()

        if interceptor.done():
            yield {"status": SessionStatus.STOPPED.name}
            return

        interceptor.cancel()

        # TODO: this is terrible, fix it
        await sleep(0.5)

        session = self.session_repo.get_session_by_session_id(
            session_id, run=run
        )
        assert session

        yield {"status": session.status.name}

    def send_command(self, command: str) -> None:
        self.command_queue.put_nowait(command)
