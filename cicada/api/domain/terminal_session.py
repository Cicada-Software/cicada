from asyncio import Event
from collections.abc import AsyncIterator, Callable

LineCallback = Callable[[str], None]


class TerminalSession:
    """
    This class represents a terminal session object, that is, it emulates the
    ability to syncrounously write lines to an object, while another service
    asyncronously reads lines as they are being appended.

    In addition to reading/writing lines, there needs to be a way to stop the
    terminal session. To stop the terminal mid execution, call finish(). This
    will stop the reader from reading any more lines, but will not stop the
    writer from writing more lines. The writing service is responsible for
    stopping itself. In addition, other services may call finish(), which means
    the writing service should also periodically check to make sure the
    terminal has not been aborted.
    """

    lines: list[str]
    has_new_line: Event
    # TODO: remove
    is_done: bool
    callback: LineCallback | None
    should_stop: Event

    def __init__(self, callback: LineCallback | None = None) -> None:
        self.lines = []
        self.has_new_line = Event()
        self.is_done = False
        self.callback = callback
        self.should_stop = Event()

    def handle_line(self, line: str) -> None:
        self.lines.append(line)
        self.has_new_line.set()

        if self.callback:
            self.callback(line)

    async def stream_batched_lines(
        self,
    ) -> AsyncIterator[list[str]]:
        index = 0

        while True:
            total_lines = len(self.lines)

            if index < total_lines:
                yield self.lines[index:total_lines]
                index = total_lines
                continue

            if self.is_done:
                break

            await self.has_new_line.wait()
            self.has_new_line.clear()

    def finish(self) -> None:
        self.has_new_line.set()
        self.is_done = True
