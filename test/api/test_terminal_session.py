import asyncio

from cicada.api.domain.terminal_session import TerminalSession


async def test_if_session_is_over_results_are_returned_immediately() -> None:
    session = TerminalSession()

    session.handle_line("line 1")
    session.handle_line("line 2")
    session.handle_line("line 3")
    session.finish()

    batches = [lines async for lines in session.stream_batched_lines()]

    assert batches == [["line 1", "line 2", "line 3"]]


async def test_lines_added_while_streaming_are_picked_up() -> None:
    session = TerminalSession()
    stream = session.stream_batched_lines()

    session.handle_line("line 1")
    assert (await anext(stream))[0] == "line 1"

    session.handle_line("line 2")
    assert (await anext(stream))[0] == "line 2"


async def test_lines_can_be_added_while_waiting() -> None:
    session = TerminalSession()

    async def add_line_in_background() -> None:
        await asyncio.sleep(0.1)
        session.handle_line("added line")

    task = asyncio.create_task(add_line_in_background())

    batch = await anext(session.stream_batched_lines())
    assert batch[0] == "added line"

    await task


async def test_terminal_session_can_be_replayed_after_closing() -> None:
    session = TerminalSession()

    sent_lines = ["line 1", "line 2", "line 3"]

    for line in sent_lines:
        session.handle_line(line)

    session.finish()

    batches = [line async for line in session.stream_batched_lines()]
    batches_replayed = [line async for line in session.stream_batched_lines()]

    assert batches == batches_replayed == [sent_lines]
