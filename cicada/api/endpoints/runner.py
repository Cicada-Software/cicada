import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

from cicada.api.endpoints.di import Di
from cicada.common.json import asjson
from cicada.domain.runner import RunnerId
from cicada.domain.session import SessionStatus
from cicada.domain.terminal_session import TerminalSession

router = APIRouter()

PROTOCOL_VERSION = 1
MINIMUM_PROTOCOL_VERSION = 1


@router.websocket("/ws/runner/connect/{runner_id}")
async def runner(
    websocket: WebSocket, di: Di, runner_id: UUID
) -> None:  # pragma: no cover
    runner_repo = di.runner_repo()
    session_repo = di.session_repo()

    try:
        await websocket.accept()

        try:
            runner_secret = websocket.headers["X-RunnerSecret"]

        except KeyError:
            return await websocket.close(
                code=1001,
                reason="Runner secret not set",
            )

        runner = runner_repo.get_runner_by_id(RunnerId(runner_id))

        if not (runner and runner.verify(runner_secret)):
            return await websocket.close(code=1001, reason="Unauthorized")

        # TODO: store in dataclass instead
        await websocket.send_json(
            {
                "type": "connect",
                "protocol_version": PROTOCOL_VERSION,
                "minimum_version": MINIMUM_PROTOCOL_VERSION,
            }
        )

        while True:
            await websocket.send_json({"type": "ping"})

            queue = runner_repo.get_queued_sessions_for_runner(runner.id)

            for session, _, url in queue:
                # TODO: store in dataclass instead
                await websocket.send_json(
                    {
                        "type": "new_workflow",
                        "session": {
                            "id": str(session.id),
                            "run": session.run,
                            "trigger": asjson(session.trigger),
                        },
                        "url": url,
                    }
                )
                # TODO: add timeout
                accept = await websocket.receive_json()

                # TODO: dont assume packets have these fields
                if not (
                    accept["session_id"] == str(session.id)
                    and accept["session_run"] == session.run
                ):
                    # Malformed packet. At some point send this back to the
                    # user, but for now just ignore it and move on

                    continue

                # Update status to pending
                session.status = SessionStatus.PENDING
                session_repo.update(session)

                workflow_id = session_repo.get_workflow_id_from_session(
                    session
                )
                assert workflow_id

                terminal_session_repo = di.terminal_session_repo()

                terminal = terminal_session_repo.get_by_workflow_id(
                    workflow_id
                )
                assert terminal

                session_running = True

                async def session_stopper(terminal: TerminalSession) -> None:
                    await terminal.should_stop.wait()

                    await websocket.send_json(
                        {
                            "type": "stop_workflow",
                            "session": {
                                "id": str(session.id),  # noqa: B023
                                "run": session.run,  # noqa: B023
                            },
                        }
                    )

                    nonlocal session_running
                    session_running = False

                task = asyncio.create_task(session_stopper(terminal))

                while session_running:
                    packet = await websocket.receive_json()

                    if not (
                        packet["session_id"] == str(session.id)
                        and packet["session_run"] == session.run
                    ):
                        # Malformed packet. At some point send this back to the
                        # user, but for now just ignore it and move on

                        continue

                    if packet["type"] == "update_workflow":
                        if stdout := packet.get("stdout"):
                            terminal.append(stdout.encode())

                        if status := packet.get("status"):
                            session.finish(SessionStatus(status))
                            session_repo.update(session)

                            break

                task.cancel()

            await asyncio.sleep(1)

    # TODO: handle cancel error
    except (WebSocketDisconnect, ConnectionClosed):
        pass
