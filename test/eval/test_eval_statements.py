import pytest

from cicada.ast.entry import parse_and_analyze
from cicada.ast.nodes import RecordValue, StringValue
from cicada.ast.semantic_analysis import IgnoreWorkflow
from cicada.ast.types import RecordField, RecordType, StringType
from cicada.domain.triggers import (
    CommitTrigger,
    GitSha,
    IssueOpenTrigger,
    Trigger,
)
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


def test_on_statement_continues_execution_if_trigger_matches() -> None:
    trigger = make_dummy_commit_trigger()

    tree = parse_and_analyze("on git.push\nlet var = 123", trigger)

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

    assert "var" in visitor.symbols


def test_on_statement_stops_execution_if_trigger_doesnt_match() -> None:
    trigger = make_dummy_issue_open_trigger()

    # TODO: wrap this in function that doesnt throw exception
    with pytest.raises(IgnoreWorkflow):
        parse_and_analyze("on x\nlet var = 123", trigger)


def test_on_statement_stops_execution_if_trigger_doesnt_match_at_runtime() -> (
    None
):
    trigger = make_dummy_issue_open_trigger()

    tree = parse_and_analyze(
        "on git.push\nlet var = 123", trigger, validate=False
    )

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

    assert "var" not in visitor.symbols


def test_on_statement_stops_execution_if_where_clause_is_false() -> None:
    trigger = make_dummy_commit_trigger()

    tree = parse_and_analyze("on git.push where false\nlet var = 123", trigger)

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

    assert "var" not in visitor.symbols


def test_on_statement_continues_execution_if_where_clause_is_true() -> None:
    trigger = make_dummy_commit_trigger()

    tree = parse_and_analyze("on git.push where true\nlet var = 123", trigger)

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

    assert "var" in visitor.symbols


def test_on_statement_converts_trigger_data_to_record() -> None:
    trigger = make_dummy_commit_trigger()

    tree = parse_and_analyze("on git.push", trigger)

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

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
                fields=[
                    RecordField("author", StringType()),
                    RecordField("branch", StringType()),
                    RecordField("committed_on", StringType()),
                    RecordField("env", RecordType()),
                    RecordField("message", StringType()),
                    RecordField("provider", StringType()),
                    RecordField("ref", StringType()),
                    RecordField("repository_url", StringType()),
                    RecordField("secret", RecordType()),
                    RecordField("sha", StringType()),
                    RecordField("type", StringType()),
                ]
            ),
        ):
            return

    pytest.fail(f"event does not match: {event}")


def test_run_on_statement_does_nothing_at_runtime() -> None:
    tree = parse_and_analyze("run_on image alpine\nlet x = 1")

    visitor = EvalVisitor()
    tree.accept(visitor)

    assert "x" in visitor.symbols
