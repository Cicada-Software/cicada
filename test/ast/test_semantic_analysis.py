import re
from pathlib import Path

import pytest

from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import AstError, generate_ast_tree
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanExpression,
    ElifExpression,
    Expression,
    FileNode,
    ForStatement,
    FunctionAnnotation,
    FunctionDefStatement,
    FunctionExpression,
    IdentifierExpression,
    IfExpression,
    ImportStatement,
    LetExpression,
    LineInfo,
    ListExpression,
    MemberExpression,
    NumericExpression,
    OnStatement,
    ParenthesisExpression,
    RecordValue,
    ShellEscapeExpression,
    StringExpression,
    StringValue,
    TitleStatement,
    ToStringExpression,
)
from cicada.ast.semantic_analysis import RESERVED_NAMES, SemanticAnalysisVisitor
from cicada.ast.types import (
    BooleanType,
    CommandType,
    FunctionType,
    ListType,
    NumericType,
    RecordType,
    StringType,
    UnionType,
    UnitType,
    UnknownType,
)
from cicada.domain.datetime import Datetime
from cicada.domain.triggers import CommitTrigger, GitSha
from cicada.parse.tokenize import tokenize
from test.ast.common import build_trigger


async def test_basic_function_call_is_valid() -> None:
    tree = await parse_and_analyze("shell echo hi")

    assert tree

    match tree.exprs[0]:
        case FunctionExpression(
            callee=IdentifierExpression("shell"),
            args=[
                StringExpression("echo"),
                StringExpression("hi"),
            ],
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_unknown_variable_causes_error() -> None:
    msg = "Variable `unknown` is not defined"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("unknown")


async def test_undefined_variable_causes_error() -> None:
    with pytest.raises(AstError, match="Variable `x` is not defined"):
        await parse_and_analyze("let y = x")


async def test_boolean_not_on_non_bool_fails() -> None:
    msg = "Cannot use `not` operator with non-boolean value"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("let x = not 1")


async def test_negation_on_non_numeric_fails() -> None:
    msg = "Cannot use `-` operator with non-numeric value"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("let x = - false")


@pytest.mark.xfail(reason="Need a way to create non-constexpr values in DSL")
async def test_on_statement_where_clause_must_be_const_expr() -> None:
    msg = "`where` clause must be a constant expression"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("let x = false\non abc where x", build_trigger("abc"))


async def test_on_statement_where_clause_must_be_bool() -> None:
    msg = "`where` clause must be a boolean type"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("on abc where 123", build_trigger("abc"))


async def test_lhs_of_member_expr_cannot_be_identifier() -> None:
    msg = "Member `a` does not exist on `x`"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("let x = 123\nlet y = x.a")


async def test_record_lhs_of_member_expr_must_exist() -> None:
    msg = "Member `doesnt_exist` does not exist on `event`"

    trigger = build_trigger("a")

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("let x = event.doesnt_exist", trigger)


async def test_binary_exprs_must_be_of_same_type() -> None:
    msg = "Expression of type `bool` cannot be used with type `number`"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("let x = 1 + true")


async def test_binary_expr_must_be_an_allowed_type() -> None:
    msg = "Expected type `number`, got type `bool` instead"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("let x = true * true")


async def test_binary_expr_error_message_with_multiple_allowed_types() -> None:
    msg = "Expected type `number`, or `string`, got type `bool` instead"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("let x = true + true")


async def test_constexpr_propagation() -> None:
    tree = await parse_and_analyze(
        """\
# these are constexpr
let a = 1 + 2
let b = not true
let c = a + 3
let d = not b
"""
    )

    assert tree

    match tree.exprs:
        case [
            LetExpression(name="a", expr=Expression(is_constexpr=True), is_constexpr=True),
            LetExpression(name="b", expr=Expression(is_constexpr=True), is_constexpr=True),
            LetExpression(name="c", expr=Expression(is_constexpr=True), is_constexpr=True),
            LetExpression(name="d", expr=Expression(is_constexpr=True), is_constexpr=True),
        ]:
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_binary_expr_types_match_operator() -> None:
    tree = await parse_and_analyze(
        """\
# these result in boolean types
let b1 = 1 is 2
let b2 = 1 < 2
let b3 = true and false

# these result in numeric types
let n1 = 1 + 2
let n2 = 1 and 2

# these result in string types
let s1 = "abc" + "123"
"""
    )

    assert tree

    match tree.exprs:
        case [
            LetExpression(
                name="b1",
                expr=BinaryExpression(
                    lhs=NumericExpression(value=1),
                    oper=BinaryOperator.IS,
                    rhs=NumericExpression(value=2),
                    type=BooleanType(),
                ),
                type=BooleanType(),
            ),
            LetExpression(
                name="b2",
                expr=BinaryExpression(
                    lhs=NumericExpression(value=1),
                    oper=BinaryOperator.LESS_THAN,
                    rhs=NumericExpression(value=2),
                    type=BooleanType(),
                ),
                type=BooleanType(),
            ),
            LetExpression(
                name="b3",
                expr=BinaryExpression(
                    lhs=BooleanExpression(value=True),
                    oper=BinaryOperator.AND,
                    rhs=BooleanExpression(value=False),
                    type=BooleanType(),
                ),
                type=BooleanType(),
            ),
            LetExpression(
                name="n1",
                expr=BinaryExpression(
                    lhs=NumericExpression(value=1),
                    oper=BinaryOperator.ADD,
                    rhs=NumericExpression(value=2),
                    type=NumericType(),
                ),
                type=NumericType(),
            ),
            LetExpression(
                name="n2",
                expr=BinaryExpression(
                    lhs=NumericExpression(value=1),
                    oper=BinaryOperator.AND,
                    rhs=NumericExpression(value=2),
                    type=NumericType(),
                ),
                type=NumericType(),
            ),
            LetExpression(
                name="s1",
                expr=BinaryExpression(
                    lhs=StringExpression(value="abc"),
                    oper=BinaryOperator.ADD,
                    rhs=StringExpression(value="123"),
                    type=StringType(),
                ),
                type=StringType(),
            ),
        ]:
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_cannot_use_non_constexpr_stmt_before_on_stmt() -> None:
    msg = "Cannot use `on` statement after a function call"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("echo hi\non x")


async def test_cannot_use_non_constexpr_stmt_before_run_on_stmt() -> None:
    msg = "Cannot use `run_on` statement after a function call"

    code = """\
echo hi
run_on image alpine
"""

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code)


async def test_cannot_use_multiple_on_stmts() -> None:
    msg = "Cannot use multiple `on` statements in a single file"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("on a\non b", build_trigger("a"))


async def test_cannot_use_multiple_run_on_stmts() -> None:
    msg = "Cannot use multiple `run_on` statements in a single file"

    code = """\
run_on image alpine
run_on image ubuntu
"""

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code)


async def test_variable_name_cannot_by_reserved_name() -> None:
    for name in RESERVED_NAMES:
        msg = f"Name `{name}` is reserved"

        with pytest.raises(AstError, match=msg):
            await parse_and_analyze(f"let {name} = 123")


async def test_type_checking_of_event_triggers() -> None:
    code = 'on git.push where event.sha is "deadbeef"'

    trigger = CommitTrigger(
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="dosisod",
        message="message",
        committed_on=Datetime.fromisoformat("2023-03-10T10:25:00-08:00"),
        repository_url="https://github.com/user/repo",
        provider="github",
    )

    tokens = tokenize(code)

    visitor = SemanticAnalysisVisitor(trigger)
    tree = generate_ast_tree(tokens)
    await tree.accept(visitor)

    assert tree

    match tree.exprs:
        case [
            OnStatement(
                "git.push",
                where=BinaryExpression(
                    lhs=MemberExpression(
                        lhs=IdentifierExpression("event"),
                        name="sha",
                        type=StringType(),
                        is_constexpr=True,
                    ),
                    oper=BinaryOperator.IS,
                    rhs=StringExpression(),
                    type=BooleanType(),
                    is_constexpr=True,
                ),
            )
        ]:
            event = visitor.symbols["event"]

            assert isinstance(event, RecordValue)
            assert event.value["sha"] == StringValue("deadbeef")

            return

    pytest.fail(f"tree does not match: {tree}")


async def test_on_statement_requires_trigger() -> None:
    msg = "Cannot use `on` statement when trigger is not defined"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("on git.push")


async def test_environment_variable_semantics() -> None:
    code = "let x = env.HELLO"

    tokens = tokenize(code)

    trigger = CommitTrigger(
        sha=GitSha("deadbeef"),
        ref="refs/heads/master",
        author="dosisod",
        message="message",
        committed_on=Datetime.fromisoformat("2023-03-10T10:25:00-08:00"),
        repository_url="https://github.com/user/repo",
        provider="github",
        env={"HELLO": "world"},
    )

    visitor = SemanticAnalysisVisitor(trigger)
    tree = generate_ast_tree(tokens)
    await tree.accept(visitor)

    match visitor.symbols["env"]:
        case RecordValue(
            value={"HELLO": StringValue("world")},
            type=RecordType({"HELLO": StringType()}),
        ):
            pass

        case _:
            pytest.fail(f"Pattern did not match: {visitor.symbols['env']}")

    symbol = visitor.symbols["x"]

    match symbol:
        case LetExpression(expr=Expression(type=StringType())):
            return

    pytest.fail(f"Tree did not match: {symbol}")


async def test_ast_error_with_filename() -> None:
    err = AstError("Test", LineInfo(1, 2, 1, 2))

    assert str(err) == "<unknown>:1:2: Test"

    err.filename = "file.ci"

    assert str(err) == "file.ci:1:2: Test"


async def test_if_expr_condition_must_be_bool_like() -> None:
    msg = "Type `record` cannot be converted to bool"

    # TODO: replace "event" with different type once more exprs types are added
    code = """\
if event:
    echo nope
"""

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code, trigger=build_trigger("xyz"))


@pytest.mark.xfail()
async def test_if_expr_must_have_body() -> None:
    code = """\
if true:
    # comment
"""

    with pytest.raises(AstError, match="If expression must have body"):
        await parse_and_analyze(code)


async def test_if_expr_creates_its_own_scope() -> None:
    code = """\
if true:
    let x = 1

echo (x)
"""

    msg = "`x` is not defined"

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_single_func_expr_in_if_failing() -> None:
    code = """\
if true:
    echo hi
"""

    await parse_and_analyze(code)


async def test_shell_function_args_are_not_stringifyable() -> None:
    code = """\
let x =
    echo hi

echo (x)
"""

    msg = "Cannot convert type `record` to `string`"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code)


async def test_error_on_reassigning_immutable_variable() -> None:
    code = """\
let x = 123

x = 456
"""

    msg = "Cannot assign to immutable variable `x` (are you forgetting `mut`?)"

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_cannot_assign_to_non_identifiers() -> None:
    code = "123 = 456"

    msg = "You can only assign to variables"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code)


async def test_error_message_when_reassigning_improper_type() -> None:
    code = """\
let mut x = 123

x = "hello world"
"""

    msg = "`string` cannot be assigned to type `number`"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code)


async def test_non_string_types_allowed_in_interpolated_strings() -> None:
    # TODO: fix newline being required here
    code = "echo abc(123)xyz\n"

    tree = await parse_and_analyze(code)

    match tree.exprs[0]:
        case FunctionExpression(
            callee=IdentifierExpression("shell"),
            args=[
                StringExpression("echo"),
                BinaryExpression(
                    StringExpression("abc"),
                    BinaryOperator.ADD,
                    BinaryExpression(
                        ShellEscapeExpression(
                            ToStringExpression(ParenthesisExpression(NumericExpression(123))),
                        ),
                        BinaryOperator.ADD,
                        StringExpression("xyz"),
                    ),
                ),
            ],
        ):
            return

    pytest.fail(f"tree does not match: {tree.exprs[0]}")


async def test_error_message_when_assigning_non_string_value_to_env() -> None:
    code = "env.ABC = 123"

    msg = "You can only assign strings to env vars"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code, trigger=build_trigger("xyz"))


async def test_error_message_when_assigning_to_nonexistent_member_expr() -> None:
    code = "unknown.variable = 123"

    msg = "Variable `unknown` is not defined"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code)


async def test_cannot_reassign_event_exprs() -> None:
    code = "event.ABC = 123"

    msg = "Cannot reassign `event` because it is immutable"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze(code, trigger=build_trigger("xyz"))


async def test_check_return_types_of_builtin_funcs() -> None:
    code = """\
print("hello world")
hashOf("some_file")
"""

    tree = await parse_and_analyze(code)

    match tree.exprs:
        case [
            FunctionExpression(callee=IdentifierExpression("print"), type=UnitType()),
            FunctionExpression(callee=IdentifierExpression("hashOf"), type=StringType()),
        ]:
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_hash_of_requires_at_least_one_arg() -> None:
    msg = "Function `hashOf` takes at least 1 argument but was called with 0 arguments"

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze("hashOf()")


async def test_hash_of_requires_string_only_args() -> None:
    msg = "Expected type `string`, got type `number` instead"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("hashOf(1)")


async def test_proper_cache_stmt_is_valid() -> None:
    await parse_and_analyze('cache file using "key"')


async def test_cache_key_must_be_string() -> None:
    msg = "Expected `string` type, got type `number`"

    with pytest.raises(AstError, match=msg):
        await parse_and_analyze("cache file using 123")


async def test_only_one_cache_stmt_allowed_per_file() -> None:
    code = """\
cache x using "abc"
cache y using "xyz"
"""

    msg = "Cannot have multiple `cache` statements"

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_only_one_title_stmt_allowed_per_file() -> None:
    code = """\
title A
title B
"""

    msg = "Cannot have multiple `title` statements in a single file"

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_parse_valid_title_stmt() -> None:
    tree = await parse_and_analyze("title Hello world")

    match tree.exprs[0]:
        case TitleStatement(parts=[StringExpression("Hello"), StringExpression("world")]):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_basic_member_functions() -> None:
    code = """\
let x = "abc"
let y = x.starts_with("abc")
"""

    tree = await parse_and_analyze(code)

    match tree.exprs[1]:
        case LetExpression(
            "y",
            FunctionExpression(
                callee=MemberExpression(
                    lhs=IdentifierExpression("x"),
                    name="starts_with",
                    type=FunctionType(rtype=BooleanType()),
                ),
                args=[StringExpression("abc")],
                type=BooleanType(),
                is_constexpr=True,
            ),
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_member_functions_on_member_exprs() -> None:
    trigger = build_trigger("x")

    code = """\
let x = event.type.starts_with("x")
"""

    tree = await parse_and_analyze(code, trigger)

    match tree.exprs[0]:
        case LetExpression(
            "x",
            FunctionExpression(
                callee=MemberExpression(
                    lhs=MemberExpression(
                        lhs=IdentifierExpression("event"),
                        name="type",
                    ),
                    name="starts_with",
                    type=FunctionType(rtype=BooleanType()),
                ),
                args=[StringExpression("x")],
                type=BooleanType(),
                is_constexpr=True,
            ),
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_starts_with_must_have_one_arg() -> None:
    msg = "Function `starts_with` takes 1 argument but was called with 0 arguments"

    code = """\
let x = ""
let x = x.starts_with()
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)

    code = """\
let x = ""
let x = x.starts_with("y", "z")
"""

    msg = "Function `starts_with` takes 1 argument but was called with 2 arguments"

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_starts_with_must_have_string_arg() -> None:
    msg = "Expected type `string`, got type `number` instead"

    code = """\
let x = ""
let x = x.starts_with(1)
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_func_def_is_typed_correctly() -> None:
    code = """\
fn f():
  echo hi
"""

    tree = await parse_and_analyze(code)

    match tree.exprs[0]:
        case FunctionDefStatement(
            body=BlockExpression(exprs=[FunctionExpression()]),
            type=FunctionType(arg_types=[], rtype=UnitType()),
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_cannot_call_no_arg_func_with_args() -> None:
    msg = "Function `f` takes 0 arguments but was called with 1 argument"

    code = """\
fn f():
    echo hi

f(123)
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_cannot_call_single_arg_func_with_no_args() -> None:
    msg = "Function `f` takes 1 argument but was called with 0 arguments"

    code = """\
fn f(x):
    echo hi

f()
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_cannot_have_func_with_duplicate_argument_names() -> None:
    msg = "Argument `x` already exists"

    code = """\
fn f(x, x):
    echo hi
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_must_call_user_defined_functions_with_proper_types() -> None:
    msg = "Expected type `string`, got type `number` instead"

    code = """\
fn f(x):
    echo hi

f(1)
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_function_return_type_must_match_block_rtype() -> None:
    msg = "Expected type `number`, got type `string` instead"

    code = """\
fn f() -> number:
    "not a number"
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        await parse_and_analyze(code)


async def test_body_rtype_ignored_when_function_rtype_is_unit_type() -> None:
    # TODO: if explicit () unit type is used then emit an error

    code = """\
fn f():
    echo not unit type but thats ok
"""

    await parse_and_analyze(code)


async def test_access_shell_function_record_fields() -> None:
    code = """\
let cmd =
    echo hi

let a = cmd.exit_code
let b = cmd.stdout
"""

    tree = await parse_and_analyze(code)

    match tree.exprs[0]:
        case LetExpression(
            "cmd",
            expr=BlockExpression(exprs=[FunctionExpression(type=CommandType())]),
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_only_certain_annotations_are_allowed() -> None:
    code = """\
@x
fn f():
  1
"""

    expected = "Unknown annotation `@x`"

    with pytest.raises(AstError, match=re.escape(expected)):
        await parse_and_analyze(code)


async def test_valid_annotation_is_allowed() -> None:
    code = """\
@workflow
fn f():
  1
"""

    tree = await parse_and_analyze(code)

    match tree.exprs[0]:
        case FunctionDefStatement(
            annotations=[FunctionAnnotation(IdentifierExpression("workflow"))]
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_workflow_annotation_must_have_unit_return_type() -> None:
    code = """\
@workflow
fn f() -> number:
  1
"""

    expected = "`@workflow` annotated functions must have `()` return type"

    with pytest.raises(AstError, match=re.escape(expected)):
        await parse_and_analyze(code)


async def test_lists_cannot_contain_mixed_types() -> None:
    code = "let l = [1, true]"

    expected = "Expected type `number`, got type `bool`"

    with pytest.raises(AstError, match=re.escape(expected)):
        await parse_and_analyze(code)


async def test_arrays_can_be_reassigned() -> None:
    code = """\
let mut l = [1]
l = [2]
"""

    await parse_and_analyze(code)


async def test_for_stmts_must_have_list_source() -> None:
    code = """
for x in 1:
  1
"""

    expected = "Expected list type, got type `number` instead"

    with pytest.raises(AstError, match=re.escape(expected)):
        await parse_and_analyze(code)


async def test_for_stmts_have_proper_types() -> None:
    code = """\
for x in [1]:
  echo (x)
"""

    tree = await parse_and_analyze(code)

    match tree.exprs[0]:
        case ForStatement(
            name=IdentifierExpression("x", type=NumericType()),
            source=ListExpression(type=ListType(NumericType())),
            body=BlockExpression([FunctionExpression()]),
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_for_stmts_cannot_have_unknown_inner_type() -> None:
    code = """
for x in []:
  1
"""

    expected = "Cannot iterate over value of type `[<unknown>]`"

    with pytest.raises(AstError, match=re.escape(expected)):
        await parse_and_analyze(code)


async def test_elif_exprs_have_proper_types() -> None:
    # TODO: narrow if expr type when always true/false branches are found

    code = """
if false:
    1
elif true:
    "testing"
"""

    tree = await parse_and_analyze(code)

    match tree.exprs[0]:
        case IfExpression(
            condition=BooleanExpression(False),
            body=BlockExpression([NumericExpression(1)]),
            elifs=[
                ElifExpression(
                    condition=BooleanExpression(True),
                    body=BlockExpression([StringExpression("testing")]),
                    type=StringType(),
                    is_constexpr=True,
                ),
            ],
            type=UnionType((NumericType(), StringType(), UnknownType())),
            is_constexpr=True,
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_if_scopes_dont_bleed_into_elif_scope() -> None:
    expected = "Variable `x` is not defined"

    code1 = """
if false:
    let x = 123
elif true:
    let y = x
"""

    code2 = """
if let x = 123:
    echo noop
elif true:
    let y = x
"""

    for code in [code1, code2]:
        with pytest.raises(AstError, match=re.escape(expected)):
            await parse_and_analyze(code)


async def test_elif_scope_doesnt_persist_after_exit() -> None:
    expected = "Variable `x` is not defined"

    code1 = """
if false:
    echo noop
elif true:
    let x = 123

let y = x
"""

    code2 = """
if false:
    echo noop
elif let x = 123:
    echo noop

let y = x
"""

    for code in [code1, code2]:
        with pytest.raises(AstError, match=re.escape(expected)):
            await parse_and_analyze(code)


async def test_elif_condition_must_be_bool_like() -> None:
    expected = "Type `()` cannot be converted to bool"

    code = """
if false:
    1
elif print("won't work"):
    2
"""

    with pytest.raises(AstError, match=re.escape(expected)):
        await parse_and_analyze(code)


async def test_else_exprs_have_proper_types() -> None:
    code = """
if false:
    1
else:
    "testing"
"""

    tree = await parse_and_analyze(code)

    match tree.exprs[0]:
        case IfExpression(
            condition=BooleanExpression(False),
            body=BlockExpression([NumericExpression(1)]),
            else_block=BlockExpression([StringExpression("testing")]),
            type=UnionType((NumericType(), StringType())),
            is_constexpr=True,
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_if_scopes_dont_bleed_into_else_scope() -> None:
    expected = "Variable `x` is not defined"

    code1 = """
if false:
    let x = 123
else:
    let y = x
"""

    code2 = """
if let x = 123:
    echo noop
else:
    let y = x
"""

    for code in [code1, code2]:
        with pytest.raises(AstError, match=re.escape(expected)):
            await parse_and_analyze(code)


async def test_else_scope_doesnt_persist_after_exit() -> None:
    expected = "Variable `x` is not defined"

    code = """
if false:
    echo noop
else:
    let x = 123

let y = x
"""

    with pytest.raises(AstError, match=re.escape(expected)):
        await parse_and_analyze(code)


async def test_constexpr_propagation_in_if_exprs() -> None:
    async def is_if_expr_constexpr(code: str) -> bool:
        tree = await parse_and_analyze(code)

        match tree.exprs[0]:
            case IfExpression(is_constexpr=is_constexpr):
                return is_constexpr

        pytest.fail(f"expected if expr: {tree}")

    tests = {
        "if true:\n\t1": True,
        "if true:\n\techo": False,
        "if true:\n\t1\nelif true:\n\t2": True,
        "if true:\n\t1\nelif true:\n\techo": False,
        "if true:\n\t1\nelse:\n\t2": True,
        "if true:\n\t1\nelse:\n\techo": False,
    }

    for code, expected in tests.items():
        assert expected == await is_if_expr_constexpr(code)


async def test_if_expr_has_single_type_if_all_branches_return_same_type() -> None:
    code = """
if false:
    1
else:
    2
"""

    tree = await parse_and_analyze(code)

    match tree.exprs[0]:
        case IfExpression(
            condition=BooleanExpression(False),
            body=BlockExpression([NumericExpression(1)]),
            else_block=BlockExpression([NumericExpression(2)]),
            type=NumericType(),
            is_constexpr=True,
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_invalid_imports_are_caught() -> None:
    # TODO: dont require newline after import

    tests = {
        "import xyz\n": "Cannot import `xyz`: Imported files must end in `.ci`",
        "let xyz = 1\nimport xyz.ci\n": "Cannot import `xyz.ci`: Importing `xyz` would shadow existing variable/function",  # noqa: E501
        "import xyz.ci\n": "Cannot import `xyz.ci`: File does not exist",
        "import /xyz.ci\n": "Cannot import files outside of root directory",
        "import ../xyz.ci\n": "Cannot import files outside of root directory",
        "import file/../../xyz.ci\n": "Cannot import files outside of root directory",
    }

    for code, expected in tests.items():
        with pytest.raises(AstError, match=re.escape(expected)):
            await parse_and_analyze(code, file_root=Path.cwd())


async def test_import_stmt_has_proper_types() -> None:
    code = """
import imported.ci
"""

    root = Path("test/ast/data/imports").resolve()

    tree = await parse_and_analyze(code, file_root=root)

    match tree.exprs[0]:
        case ImportStatement(
            module=module,
            tree=FileNode(
                exprs=[LetExpression("x", StringExpression("imported variable"))],
            ),
        ) if module == Path("imported.ci"):
            return

    pytest.fail(f"tree does not match: {tree}")


async def test_certain_stmts_cannot_be_used_in_imported_modules() -> None:
    tests = {
        'cache x using ""': "Cannot use `cache` inside imported modules",
        "on git.push": "Cannot use `on` inside imported modules",
        "run_on image alpine": "Cannot use `run_on` inside imported modules",
        "title x": "Cannot use `title` inside imported modules",
    }

    for code, expected in tests.items():
        tokens = tokenize(code)

        visitor = SemanticAnalysisVisitor()
        visitor.is_inside_import = True

        tree = generate_ast_tree(tokens)

        with pytest.raises(AstError, match=re.escape(expected)):
            await tree.accept(visitor)


async def test_imported_modules_cannot_call_workflow_functions() -> None:
    code = """
@workflow
fn f():
    1

f()
"""

    expected = "Cannot create sub-workflow in imported modules"

    tokens = tokenize(code)

    visitor = SemanticAnalysisVisitor()
    visitor.is_inside_import = True

    tree = generate_ast_tree(tokens)

    with pytest.raises(AstError, match=re.escape(expected)):
        await tree.accept(visitor)
