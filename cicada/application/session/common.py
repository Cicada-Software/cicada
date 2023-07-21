from collections.abc import Callable, Coroutine
from pathlib import Path

from cicada.domain.session import Session
from cicada.domain.terminal_session import TerminalSession
from cicada.domain.triggers import Trigger

IWorkflowRunner = Callable[
    [Session, TerminalSession, Path],
    Coroutine[None, None, None],
]

IWorkflowGatherer = Callable[
    [Trigger, Path],
    Coroutine[None, None, list[Path]],
]
