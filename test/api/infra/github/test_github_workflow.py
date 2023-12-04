from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from cicada.api.infra.github.workflows import run_workflow
from cicada.ast.nodes import FileNode
from cicada.domain.session import Session, Workflow, WorkflowStatus
from cicada.domain.terminal_session import TerminalSession
from test.api.endpoints.common import TestDiContainer
from test.common import build


@asynccontextmanager
async def mock_github_workflow_runner() -> AsyncGenerator[dict[str, Mock], None]:
    pkg = "cicada.api.infra.github.workflows"

    with (
        patch(f"{pkg}.add_access_token_for_repository_url") as get_repo_access_token,
        patch(f"{pkg}.wrap_in_github_check_run") as wrap_in_github_check_run,
        patch(f"{pkg}.ExecutionSettings") as execution_settings,
        patch(f"{pkg}.get_execution_type") as get_execution_type,
    ):
        execution_settings.return_value = SimpleNamespace(executor="anything")

        get_execution_type.return_value.return_value = MagicMock(
            spec=SimpleNamespace(run=AsyncMock())
        )

        # TODO: find a better way to return these
        yield {
            "get_repo_access_token": get_repo_access_token,
            "wrap_in_github_check_run": wrap_in_github_check_run,
            "execution_settings": execution_settings,
            "get_execution_type": get_execution_type,
        }


async def test_run_workflow() -> None:
    session = build(Session)
    workflow = Workflow.from_session(session, filename=Path())

    async with mock_github_workflow_runner() as mocks:
        wrap_in_github_check_run = mocks["wrap_in_github_check_run"]
        get_execution_type = mocks["get_execution_type"]

        wrap_in_github_check_run.return_value = nullcontext()
        get_execution_type.return_value.return_value.run.return_value = 0

        di = TestDiContainer()

        await run_workflow(session, TerminalSession(), Path(), FileNode([]), workflow, di=di)

        assert workflow.status == WorkflowStatus.SUCCESS
        assert workflow.finished_at

        wrap_in_github_check_run.assert_called_once()

        kwargs = get_execution_type.return_value.call_args.kwargs

        assert kwargs["trigger"] == session.trigger
        assert kwargs["workflow"] == workflow


async def test_session_fails_if_exception_occurs_in_workflow() -> None:
    session = build(Session)
    workflow = Workflow.from_session(session, filename=Path())

    async with mock_github_workflow_runner() as mocks:
        wrap_in_github_check_run = mocks["wrap_in_github_check_run"]
        get_execution_type = mocks["get_execution_type"]

        wrap_in_github_check_run.return_value = nullcontext()

        async def f(_: FileNode) -> None:
            raise RuntimeError

        get_execution_type.return_value.return_value.run.side_effect = f

        di = TestDiContainer()

        with pytest.raises(RuntimeError):
            await run_workflow(
                session,
                TerminalSession(),
                Path(),
                FileNode([]),
                workflow,
                di=di,
            )

        assert workflow.status == WorkflowStatus.FAILURE
        assert workflow.finished_at
