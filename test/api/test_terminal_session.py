import asyncio

from cicada.api.domain.terminal_session import TerminalSession


async def test_if_session_is_over_results_are_returned_immediately() -> None:
    session = TerminalSession()

    session.append(b"line 1\n")
    session.append(b"line 2\n")
    session.append(b"line 3\n")
    session.finish()

    chunks = [lines async for lines in session.stream_chunks()]

    assert chunks == [b"line 1\nline 2\nline 3\n"]


async def test_lines_added_while_streaming_are_picked_up() -> None:
    session = TerminalSession()
    stream = session.stream_chunks()

    session.append(b"line 1")
    assert (await anext(stream)) == b"line 1"

    session.append(b"line 2")
    assert (await anext(stream)) == b"line 2"


async def test_lines_can_be_added_while_waiting() -> None:
    session = TerminalSession()

    async def add_data_in_background() -> None:
        await asyncio.sleep(0.1)
        session.append(b"added line")

    task = asyncio.create_task(add_data_in_background())

    chunk = await anext(session.stream_chunks())
    assert chunk == b"added line"

    await task


async def test_terminal_session_can_be_replayed_after_closing() -> None:
    session = TerminalSession()

    sent_lines = [b"line 1\n", b"line 2\n", b"line 3\n"]

    for line in sent_lines:
        session.append(line)

    session.finish()

    chunks = [line async for line in session.stream_chunks()]
    chunks_replayed = [line async for line in session.stream_chunks()]

    assert chunks == chunks_replayed == [b"".join(sent_lines)]
