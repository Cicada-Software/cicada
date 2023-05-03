from asyncio import create_task, wait_for

import pytest

from cicada.api.domain.session import SessionStatus
from cicada.api.domain.terminal_session import TerminalSession
from cicada.api.infra.run_program import exit_code_to_status_code, run_program


async def test_basic_stdout_capturing() -> None:
    terminal_session = TerminalSession()

    exit_code = await run_program(["echo", "hello world"], terminal_session)

    assert exit_code == 0
    assert terminal_session.is_done
    assert terminal_session.lines == ["hello world\n"]


async def test_long_running_process_is_awaited() -> None:
    terminal_session = TerminalSession()

    await run_program(["sleep", "0.1"], terminal_session)


async def test_exit_code_is_forwarded() -> None:
    terminal_session = TerminalSession()

    exit_code = await run_program(["false"], terminal_session)

    assert exit_code == 1
    assert terminal_session.is_done


async def test_non_existent_program_closes_terminal_session() -> None:
    terminal_session = TerminalSession()

    with pytest.raises(FileNotFoundError):
        await run_program(["non_existent_program"], terminal_session)

    assert terminal_session.is_done


async def test_exception_in_terminal_session_handler_cleans_up_session() -> None:  # noqa: E501
    terminal_session = TerminalSession()

    def callback(_: str) -> None:
        raise ValueError("This is handled")

    terminal_session.callback = callback

    with pytest.raises(ValueError, match="This is handled"):
        await run_program(["echo", "hi"], terminal_session)

    assert terminal_session.is_done


async def test_explicitly_stopping_terminal_will_kill_process() -> None:
    terminal_session = TerminalSession()

    task = create_task(run_program(["sleep", "9999"], terminal_session))

    terminal_session.should_stop.set()

    try:
        await wait_for(task, 1)

    except TimeoutError:
        pytest.fail("Program was not terminated in time")


def test_exit_code_mappings() -> None:
    tests = {
        -1: SessionStatus.STOPPED,
        0: SessionStatus.SUCCESS,
        1: SessionStatus.FAILURE,
        2: SessionStatus.FAILURE,
        3: SessionStatus.FAILURE,
    }

    for exit_code, expected in tests.items():
        assert exit_code_to_status_code(exit_code) == expected
