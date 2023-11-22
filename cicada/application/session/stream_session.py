from asyncio import Queue, create_task, sleep
from collections.abc import AsyncGenerator, Callable, Coroutine

from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.session import SessionId, WorkflowId, WorkflowStatus


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
        session = self.session_repo.get_session_by_session_id(session_id, run)
        if not session:
            yield {"error": "Session not found"}
            return

        # TODO: allow for getting workflow id by session id/run
        workflow_id = self.session_repo.get_workflow_id_from_session(session)
        if not workflow_id:
            yield {"error": "Session not found"}
            return

        workflow = self.session_repo.get_workflow_by_id(workflow_id)
        if not workflow:
            yield {"error": "Session not found"}
            return

        terminal = self.terminal_session_repo.get_by_workflow_id(workflow_id)
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

        if workflow.status == WorkflowStatus.BOOTING:
            status = await self.wait_for_status_change(workflow_id, is_booting=True)

            yield {"status": status.name}

        async for chunks in terminal.stream_chunks():
            yield {"stdout": chunks.decode()}

        terminal.finish()

        if interceptor.done():
            yield {"status": WorkflowStatus.STOPPED.name}
            return

        interceptor.cancel()

        status = await self.wait_for_status_change(workflow_id)

        yield {"status": status.name}

    async def wait_for_status_change(
        self,
        workflow_id: WorkflowId,
        is_booting: bool = False,
    ) -> WorkflowStatus:
        """
        Repeatedly check for updates to the workflow status, and return once the
        status has changed. When we are booting we are looking for a workflow
        status that isn't BOOTING, and after we have booted, we are looking for
        a workflow status that isn't PENDING. We have to wait longer for a
        workflow to start then we do for a workflow to stop since it we might
        have to wait for a self-hosted runner to become available for certain
        workflows, for example.
        """

        if is_booting:
            ignore = WorkflowStatus.BOOTING
            attempts = 1_000
        else:
            ignore = WorkflowStatus.PENDING
            attempts = 10

        for _ in range(attempts):
            workflow = self.session_repo.get_workflow_by_id(workflow_id)
            assert workflow

            if workflow.status == ignore:
                await sleep(0.5)
                continue

            return workflow.status

        # Workflow is still pending, bail and return pending status
        return WorkflowStatus.PENDING

    def send_command(self, command: str) -> None:
        self.command_queue.put_nowait(command)
