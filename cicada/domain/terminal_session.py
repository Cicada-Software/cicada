from asyncio import Event
from collections.abc import AsyncIterator, Callable


class TerminalSession:
    """
    This class represents a terminal session object, that is, it emulates the
    ability to syncrounously write chunks to an object, while another service
    asynchronously reads chunks as they are being appended.

    In addition to reading/writing chunks, there needs to be a way to stop the
    terminal session. To stop the terminal mid execution, call finish(). This
    will stop the reader from reading any more chunks, but will not stop the
    writer from writing more chunks. The writing service is responsible for
    stopping itself. In addition, other services may call finish(), which means
    the writing service should also periodically check to make sure the
    terminal has not been aborted.
    """

    chunks: list[bytes]
    has_new_chunk: Event
    # TODO: remove
    is_done: bool
    callback: Callable[[bytes], None] | None
    should_stop: Event

    def __init__(
        self, callback: Callable[[bytes], None] | None = None
    ) -> None:
        self.chunks = []
        self.has_new_chunk = Event()
        self.is_done = False
        self.callback = callback
        self.should_stop = Event()

    def append(self, data: bytes) -> None:
        self.chunks.append(data)
        self.has_new_chunk.set()

        if self.callback:
            self.callback(data)

    async def stream_chunks(
        self,
    ) -> AsyncIterator[bytes]:
        index = 0

        while True:
            total_chunks = len(self.chunks)

            if index < total_chunks:
                yield b"".join(self.chunks[index:total_chunks])
                index = total_chunks
                continue

            if self.is_done:
                break

            await self.has_new_chunk.wait()
            self.has_new_chunk.clear()

    def finish(self) -> None:
        self.has_new_chunk.set()
        self.is_done = True
