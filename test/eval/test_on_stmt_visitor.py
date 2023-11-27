import pytest

from cicada.ast.entry import parse_and_analyze
from cicada.eval.on_statement_visitor import OnStatementEvalVisitor, ShouldRunWorkflow

from .test_eval_statements import make_dummy_commit_trigger


async def test_on_statement_run_conditions() -> None:
    tests = {
        "on git.push": True,
        "on git.push where true": True,
        "on git.push where false": False,
        "echo hi": False,
        'on git.push where event.type.starts_with("git")': True,
        'on git.push where event.type.starts_with("xyz")': False,
    }

    trigger = make_dummy_commit_trigger()

    for test, should_run in tests.items():
        tree = await parse_and_analyze(test, trigger)

        visitor = OnStatementEvalVisitor(trigger)

        with pytest.raises(ShouldRunWorkflow) as ex:
            await tree.accept(visitor)

        assert ex.value.should_run == should_run
