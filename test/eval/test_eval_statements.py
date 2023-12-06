import pytest

from cicada.ast.entry import parse_and_analyze
from cicada.ast.nodes import NumericValue, RecordValue, StringValue
from cicada.ast.semantic_analysis import IgnoreWorkflow
from cicada.ast.types import RecordType, StringType
from cicada.domain.triggers import CommitTrigger, GitSha, IssueOpenTrigger, Trigger
from cicada.eval.main import EvalVisitor
from test.common import build


def make_dummy_commit_trigger() -> Trigger:
    return build(
        CommitTrigger,
        provider="github",
        sha=GitSha("DEADBEEF"),
        ref="refs/heads/master",
        author="dosisod",
    )


def make_dummy_issue_open_trigger() -> Trigger:
    return build(
        IssueOpenTrigger,
        provider="github",
        id="1",
        submitted_by="dosisod",
    )


async def test_on_statement_continues_execution_if_trigger_matches() -> None:
    trigger = make_dummy_commit_trigger()

    tree = await parse_and_analyze("on git.push\nlet var = 123", trigger)

    visitor = EvalVisitor(trigger)
    await tree.accept(visitor)

    assert "var" in visitor.symbols


async def test_on_statement_stops_execution_if_trigger_doesnt_match() -> None:
    trigger = make_dummy_issue_open_trigger()

    # TODO: wrap this in function that doesnt throw exception
    with pytest.raises(IgnoreWorkflow):
        await parse_and_analyze("on x\nlet var = 123", trigger)


async def test_on_statement_stops_execution_if_trigger_doesnt_match_at_runtime() -> None:
    trigger = make_dummy_issue_open_trigger()

    tree = await parse_and_analyze("on git.push\nlet var = 123", trigger, validate=False)

    visitor = EvalVisitor(trigger)
    await tree.accept(visitor)

    assert "var" not in visitor.symbols


async def test_on_statement_stops_execution_if_where_clause_is_false() -> None:
    trigger = make_dummy_commit_trigger()

    tree = await parse_and_analyze("on git.push where false\nlet var = 123", trigger)

    visitor = EvalVisitor(trigger)
    await tree.accept(visitor)

    assert "var" not in visitor.symbols


async def test_on_statement_continues_execution_if_where_clause_is_true() -> None:
    trigger = make_dummy_commit_trigger()

    tree = await parse_and_analyze("on git.push where true\nlet var = 123", trigger)

    visitor = EvalVisitor(trigger)
    await tree.accept(visitor)

    assert "var" in visitor.symbols


async def test_on_statement_converts_trigger_data_to_record() -> None:
    trigger = make_dummy_commit_trigger()

    tree = await parse_and_analyze("on git.push", trigger)

    visitor = EvalVisitor(trigger)
    await tree.accept(visitor)

    event = visitor.symbols.get("event")
    assert event

    match event:
        case RecordValue(
            value={
                "env": RecordValue(),
                "type": StringValue("git.push"),
                "provider": StringValue("github"),
                "repository_url": StringValue(""),
                "sha": StringValue("DEADBEEF"),
                "author": StringValue("dosisod"),
                "message": StringValue(""),
                "committed_on": StringValue(),
                "secret": RecordValue(),
            },
            type=RecordType(
                fields={
                    "author": StringType(),
                    "branch": StringType(),
                    "committed_on": StringType(),
                    "env": RecordType(),
                    "message": StringType(),
                    "provider": StringType(),
                    "ref": StringType(),
                    "repository_url": StringType(),
                    "secret": RecordType(),
                    "sha": StringType(),
                    "type": StringType(),
                }
            ),
        ):
            return

    pytest.fail(f"event does not match: {event}")


async def test_run_on_statement_does_nothing_at_runtime() -> None:
    tree = await parse_and_analyze("run_on image alpine\nlet x = 1")

    visitor = EvalVisitor()
    await tree.accept(visitor)

    assert "x" in visitor.symbols


async def test_title_statement_does_nothing_at_runtime() -> None:
    tree = await parse_and_analyze("title test\nlet x = 1")

    visitor = EvalVisitor()
    await tree.accept(visitor)

    assert "x" in visitor.symbols


async def test_for_stmt_iterates_over_values_and_doesnt_bleed_value_after_scope() -> None:
    code = """
let mut x = 0

for y in [1, 2, 3]:
    x = (x + y)
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    assert "y" not in visitor.symbols

    x = visitor.symbols["x"]

    assert isinstance(x, NumericValue)
    assert x.value == 6


async def test_nested_for_loops_work() -> None:
    code = """
let mut x = 0

for y in [1]:
    for z in [2]:
        x = (y + z)
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    assert "y" not in visitor.symbols

    x = visitor.symbols["x"]

    assert isinstance(x, NumericValue)
    assert x.value == 3
