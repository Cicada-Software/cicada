import asyncio
import json
import logging
import os
import pty
import shlex
import signal
import subprocess
import sys
import tempfile
import termios
from contextlib import suppress
from functools import partial
from pathlib import Path
from typing import Any, NoReturn

from dotenv import load_dotenv
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import ConnectionClosed

from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import AstError
from cicada.ast.nodes import (
    FunctionExpression,
    RecordValue,
    StringValue,
    UnitValue,
    Value,
)
from cicada.ast.semantic_analysis import IgnoreWorkflow
from cicada.ast.types import RecordType
from cicada.domain.session import SessionStatus
from cicada.domain.triggers import CommitTrigger, Trigger, json_to_trigger
from cicada.eval.constexpr_visitor import (
    CommandFailed,
    ConstexprEvalVisitor,
    value_to_string,
)
from cicada.eval.find_files import find_ci_files
from cicada.logging import CustomFormatter

PROTOCOL_VERSION = 1


handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())

# TODO: add log level and timestamp to each message
logger = logging.getLogger("cicada-runner")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)


logger.info("Attempting to read .env file")
load_dotenv()


RUNNER_ID = os.getenv("RUNNER_ID", "")
if not RUNNER_ID:
    logger.fatal("RUNNER_ID env var must be set!")
    sys.exit(1)


RUNNER_SECRET = os.getenv("RUNNER_SECRET", "")
if not RUNNER_SECRET:
    logger.fatal("RUNNER_SECRET env var must be set!")
    sys.exit(1)

CICADA_DOMAIN = os.getenv("CICADA_DOMAIN") or "cicada.sh"
LOG_LEVEL = (os.getenv("LOG_LEVEL") or "info").upper()

logger.setLevel(LOG_LEVEL)


TASK_QUEUE: dict[tuple[str, int], asyncio.Task[None]] = {}


async def send_json(  # type: ignore
    ws: WebSocketClientProtocol, data: str | dict[str, Any]
) -> None:
    if not isinstance(data, str):
        data = json.dumps(data, separators=(",", ":"))

    logger.debug(f"Sending packet: {data}")

    await ws.send(data)


async def recv_json(  # type: ignore[misc]
    ws: WebSocketClientProtocol,
) -> dict[str, Any]:
    packet = await ws.recv()

    if isinstance(packet, bytes):
        packet = packet.decode()

    logger.debug(f"Received packet: {packet}")

    return json.loads(packet)  # type: ignore


def add_control_c_handler() -> None:
    logger.info(f"Connecting to {CICADA_DOMAIN}")

    def close(*_) -> NoReturn:  # type: ignore
        logger.fatal("Shutting down")
        os._exit(0)  # noqa: SLF001

    signal.signal(signal.SIGINT, close)
    signal.signal(signal.SIGTERM, close)


# TODO: rewrite as a state machine
async def run() -> None:
    add_control_c_handler()

    connection = connect(
        f"wss://{CICADA_DOMAIN}/ws/runner/connect/{RUNNER_ID}",
        extra_headers={"X-RunnerSecret": RUNNER_SECRET},
        ping_interval=None,
        ping_timeout=None,
    )

    async for ws in connection:
        try:
            await websocket_lifecycle(ws)
            break

        except ConnectionClosed as ex:
            if ex.rcvd and ex.rcvd.code == 1001:
                logger.fatal(
                    "Connection failed: Unauthorized (is RUNNER_SECRET valid?)"
                )
                break

            logger.warning("Connection closed, reconnecting")

        except Exception:
            logger.exception("Fatal error:")
            break


async def websocket_lifecycle(ws: WebSocketClientProtocol) -> None:
    async def close(*_) -> NoReturn:  # type: ignore
        logger.fatal("Shutting down")
        await ws.close()
        os._exit(0)  # noqa: SLF001

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: loop.create_task(close()))
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(close()))

    # handle initial connection
    initial = await recv_json(ws)

    if initial["type"] != "connect":
        err = "Expected `connect` packet type"
        logger.error(err)
        await ws.close(1003, err)
        return

    minimum_version = initial["minimum_version"]

    if minimum_version > PROTOCOL_VERSION:
        err = f"Runner is using protocol v{PROTOCOL_VERSION}, but server requires protocol v{minimum_version}"  # noqa: E501

        logger.error(err)
        await ws.close(1003, err)
        return

    logger.info("Connection successful")

    while True:
        packet = await recv_json(ws)

        if packet["type"] == "ping":
            # Do nothing. Used to keep the connection open.
            pass

        elif packet["type"] == "new_workflow":
            session_id = packet["session"]["id"]
            session_run = packet["session"]["run"]

            task = asyncio.create_task(handle_new_workflow_packet(ws, packet))
            TASK_QUEUE[(session_id, session_run)] = task

            def pop(id: str = session_id, run: int = session_run) -> None:
                TASK_QUEUE.pop((id, run), None)

            task.add_done_callback(lambda _: pop())

        elif packet["type"] == "stop_workflow":
            logger.info("Stopping session")
            session_id = packet["session"]["id"]
            session_run = packet["session"]["run"]

            task = TASK_QUEUE.pop((session_id, session_run))

            task.cancel()
            logger.info("Session stopped")

        else:
            logger.error(f"Unknown packet type: {packet['type']}")
            await ws.close(1003)
            return


async def handle_new_workflow_packet(  # type: ignore[misc]
    ws: WebSocketClientProtocol,
    packet: dict[str, Any],
) -> None:
    session_id = packet["session"]["id"]
    session_run = packet["session"]["run"]

    logger.info("Accepting new workflow")

    await send_json(
        ws,
        {
            "session_id": session_id,
            "session_run": session_run,
        },
    )

    logger.info("Workflow accepted")

    data_stream: list[bytes] = []

    async def stream_reader() -> None:
        while True:
            new_data = data_stream.copy()

            if not new_data:
                await asyncio.sleep(0.1)
                continue

            # In case data has been written since we last read, only pop the
            # data that we copied.
            del data_stream[: len(new_data)]

            await send_json(
                ws,
                {
                    "type": "update_workflow",
                    "session_id": session_id,
                    "session_run": session_run,
                    "stdout": b"".join(new_data).decode(),
                },
            )

    task = asyncio.create_task(stream_reader())

    logger.info("Running workflow")

    status = await run_session(
        packet,
        data_stream,
        asyncio.Event(),
    )

    # Add small delay to let reader finish sending stdout
    await asyncio.sleep(0.5)

    task.cancel()

    logger.info("Finishing workflow")
    await send_json(
        ws,
        {
            "type": "update_workflow",
            "session_id": session_id,
            "session_run": session_run,
            "status": status.name,
        },
    )

    logger.info("Finished workflow")


async def checkout_branch_from_trigger(trigger: Trigger) -> None:
    ref = (
        "/".join(trigger.ref.split("/")[2:])
        if isinstance(trigger, CommitTrigger)
        else "HEAD"
    )

    sha = str(trigger.sha)

    if ref and sha:
        git_command_args = (
            ("checkout", ref),
            ("reset", "--hard", sha),
        )

        for args in git_command_args:
            proc = await asyncio.subprocess.create_subprocess_exec(
                "git",
                *args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            await proc.wait()


async def run_session(  # type: ignore[misc]
    payload: dict[str, Any],
    data_stream: list[bytes],
    should_stop: asyncio.Event,
) -> SessionStatus:
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)

        proc = await asyncio.subprocess.create_subprocess_exec(
            "git",
            "clone",
            shlex.quote(payload["url"]),
            "-q",
        )

        await proc.wait()

        # cd into newly cloned repo
        os.chdir(next(Path(tmp).iterdir()))

        trigger = json_to_trigger(json.dumps(payload["session"]["trigger"]))

        await checkout_branch_from_trigger(trigger)

        if proc.returncode != 0:
            data_stream.append(b"Error, could not clone repository")

            return SessionStatus.FAILURE

        for file in find_ci_files(Path(tmp)):
            status = await run_workflow(
                file,
                trigger,
                data_stream,
                should_stop,
            )

            if status is not None:
                return status

    logger.error("No runnable CI files found")
    return SessionStatus.FAILURE


async def run_workflow(
    file: Path,
    trigger: Trigger,
    data_stream: list[bytes],
    should_stop: asyncio.Event,
) -> SessionStatus | None:
    try:
        tree = parse_and_analyze(file.read_text(), trigger)

    except IgnoreWorkflow:
        return None

    except AstError as err:
        err.filename = str(file)
        logger.exception("Cannot run workflow due to AST error:")
        return None

    try:
        visitor = SelfHostedVisitor(data_stream, should_stop, trigger)

        fut = asyncio.get_event_loop().run_in_executor(
            None,
            partial(tree.accept, visitor),  # type: ignore
        )

        async def workflow_stopper() -> None:
            await should_stop.wait()
            fut.cancel()

        task = asyncio.create_task(workflow_stopper())

        try:
            await fut

        except asyncio.CancelledError:
            return SessionStatus.STOPPED

        task.cancel()

    except CommandFailed:
        return SessionStatus.FAILURE

    return SessionStatus.SUCCESS


class SelfHostedVisitor(ConstexprEvalVisitor):
    def __init__(
        self,
        data_stream: list[bytes],
        stopper: asyncio.Event,
        trigger: Trigger | None = None,
    ) -> None:
        super().__init__(trigger)

        self.data_stream = data_stream
        self.should_stop = stopper

    def terminate_if_needed(self) -> None:
        """
        If the callee has already cancelled then we should exit as soon as
        possible. No stdout data will be sent back, so there is no need to keep
        running.
        """

        if self.should_stop.is_set():
            raise CommandFailed(1)

    def visit_func_expr(self, node: FunctionExpression) -> Value:
        self.terminate_if_needed()

        args: list[str] = []

        for arg in node.args:
            value = value_to_string(arg.accept(self))

            assert isinstance(value, StringValue)

            args.append(value.value)

        if node.name == "shell":
            # Hacky tty magic from: https://stackoverflow.com/a/28925318
            master, slave = pty.openpty()

            with suppress(termios.error):
                # Attempt to set TTY to desired max_column size. This might
                # fail, so we suppress the error. This is probably due to the
                # terminal not supporting the ability to resize the terminal.
                lines, _ = termios.tcgetwinsize(sys.stdout)
                termios.tcsetwinsize(sys.stdout, (lines, 120))

            process = subprocess.Popen(
                [  # noqa: S603
                    "/bin/sh",
                    "-c",
                    shlex.join(args),
                ],
                stdout=slave,
                stderr=subprocess.STDOUT,
                close_fds=True,
                env=self.trigger.env if self.trigger else None,
            )

            os.close(slave)

            with suppress(IOError):
                while True:
                    self.terminate_if_needed()

                    data = os.read(master, 1024)

                    if not data:
                        break

                    self.data_stream.append(data)

            returncode = process.wait()

            if returncode != 0:
                raise CommandFailed(returncode)

            # TODO: return rich "command type" value
            return RecordValue({}, RecordType())

        if node.name == "print":
            self.data_stream.append(" ".join(args).encode())

        return UnitValue()


asyncio.run(run())
