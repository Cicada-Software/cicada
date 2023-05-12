from collections.abc import Callable, Coroutine
from pathlib import Path

from cicada.api.domain.session import Session
from cicada.api.domain.terminal_session import TerminalSession
from cicada.api.domain.triggers import Trigger

# TODO: relocate this file

IWorkflowRunner = Callable[
    [Session, TerminalSession, Path],
    Coroutine[None, None, None],
]

IWorkflowGatherer = Callable[
    [Trigger, Path],
    Coroutine[None, None, list[Path]],
]
