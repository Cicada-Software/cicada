import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from cicada.api.application.session.make_session_from_trigger import (
    MakeSessionFromTrigger,
)
from cicada.api.common.datetime import UtcDatetime
from cicada.api.domain.session import Session, SessionStatus
from cicada.api.domain.terminal_session import TerminalSession
from cicada.api.domain.triggers import CommitTrigger, GitSha


class AsyncTap:
    """
    This class is used for reliably stopping execution of an async function at
    a specified point. To use, create an async function which waits for the tap
    to be closed, then pass this function to the code you want to test. In your
    test, open the tap (which will stop the execution wherever the await in
    your async function was), and once the tap is closed, your async function
    will continue to run.
    """

    def __init__(self) -> None:
        self.prod = asyncio.Event()
        self.test = asyncio.Event()

    async def wait_for_close(self) -> None:
        self.prod.set()
        await self.test.wait()

    @asynccontextmanager
    async def open(self) -> AsyncGenerator[None, None]:
        await self.prod.wait()
        yield
        self.test.set()


async def test_session_is_created() -> None:
    tap = AsyncTap()

    async def dummy_check_runner(session: Session, _: TerminalSession) -> None:
        await tap.wait_for_close()

        session.finish(SessionStatus.SUCCESS)

    session_repo = MagicMock()
    terminal_session_repo = MagicMock()

    terminal_session = TerminalSession()
    terminal_session_repo.create.return_value = terminal_session

    cmd = MakeSessionFromTrigger(
        session_repo,
        terminal_session_repo,
        dummy_check_runner,
        gather_workflows=AsyncMock(return_value=[1]),
    )

    commit = CommitTrigger(
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="",
        message="",
        committed_on=UtcDatetime.now(),
        repository_url="",
        provider="github",
    )

    handle = asyncio.create_task(cmd.handle(commit))

    session_repo.create.called_once()

    # stop execution during workflow runner execution, check that the session
    # hasn't finished, that it was passed the correct args, etc.
    async with tap.open():
        new_session: Session = session_repo.create.call_args[0][0]

        assert new_session.trigger == commit
        assert not new_session.finished_at

    # finish the rest of the workflow
    await handle

    updated_session: Session = session_repo.update.call_args[0][0]

    assert updated_session.finished_at


async def test_session_not_created_if_workflow_gather_fails() -> None:
    session_repo = MagicMock()
    terminal_session_repo = MagicMock()

    cmd = MakeSessionFromTrigger(
        session_repo,
        terminal_session_repo,
        workflow_runner=AsyncMock(),
        gather_workflows=AsyncMock(return_value=[]),
    )

    commit = CommitTrigger(
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="",
        message="",
        committed_on=UtcDatetime.now(),
        repository_url="",
        provider="github",
    )

    await cmd.handle(commit)

    session_repo.create.assert_not_called()
    terminal_session_repo.create.assert_not_called()
