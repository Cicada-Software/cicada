from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, nullcontext
from typing import cast
from unittest.mock import Mock, patch

import pytest

from cicada.api.common.json import asjson
from cicada.api.domain.session import SessionStatus
from cicada.api.domain.terminal_session import TerminalSession
from cicada.api.infra.github.workflows import run_workflow
from cicada.api.infra.run_program import ExecutionContext
from test.api.infra.test_session_repo import create_dummy_session


@asynccontextmanager
async def mock_github_workflow_runner() -> AsyncGenerator[
    dict[str, Mock], None
]:
    pkg = "cicada.api.infra.github.workflows"

    with (
        patch(f"{pkg}.get_repo_access_token") as get_repo_access_token,
        patch(f"{pkg}.wrap_in_github_check_run") as wrap_in_github_check_run,
        patch(f"{pkg}.run_docker_workflow") as run_docker_workflow,
    ):
        # TODO: find a better way to return these
        yield {
            "get_repo_access_token": get_repo_access_token,
            "wrap_in_github_check_run": wrap_in_github_check_run,
            "run_docker_workflow": run_docker_workflow,
        }


async def test_run_workflow() -> None:
    session = create_dummy_session()

    async with mock_github_workflow_runner() as mocks:
        get_repo_access_token = mocks["get_repo_access_token"]
        wrap_in_github_check_run = mocks["wrap_in_github_check_run"]
        run_docker_workflow = mocks["run_docker_workflow"]

        get_repo_access_token.return_value = "access_token"
        wrap_in_github_check_run.return_value = nullcontext()
        run_docker_workflow.return_value = 0

        await run_workflow(session, TerminalSession(), {})

        assert session.status == SessionStatus.SUCCESS
        assert session.finished_at

        get_repo_access_token.assert_called_once()
        wrap_in_github_check_run.assert_called_once()

        ctx = cast(ExecutionContext, run_docker_workflow.call_args[0][0])

        assert (
            ctx.url == "https://access_token:access_token@github.com/user/repo"
        )
        assert ctx.trigger_type == "git.push"
        assert ctx.trigger == asjson(session.trigger)


async def test_session_fails_if_exception_occurs_in_workflow() -> None:
    session = create_dummy_session()

    async with mock_github_workflow_runner() as mocks:
        get_repo_access_token = mocks["get_repo_access_token"]
        wrap_in_github_check_run = mocks["wrap_in_github_check_run"]
        run_docker_workflow = mocks["run_docker_workflow"]

        get_repo_access_token.return_value = "access_token"
        wrap_in_github_check_run.return_value = nullcontext()

        async def f(_) -> None:  # type: ignore
            raise RuntimeError()

        run_docker_workflow.side_effect = f

        with pytest.raises(RuntimeError):
            await run_workflow(session, TerminalSession(), {})

        assert session.status == SessionStatus.FAILURE
        assert session.finished_at
