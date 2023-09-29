import re

import pytest

from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import AstError, generate_ast_tree
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanExpression,
    Expression,
    FunctionDefStatement,
    FunctionExpression,
    IdentifierExpression,
    LetExpression,
    LineInfo,
    MemberExpression,
    NumericExpression,
    OnStatement,
    ParenthesisExpression,
    RecordValue,
    StringExpression,
    StringValue,
    TitleStatement,
    ToStringExpression,
)
from cicada.ast.semantic_analysis import (
    RESERVED_NAMES,
    SemanticAnalysisVisitor,
)
from cicada.ast.types import (
    BooleanType,
    CommandType,
    FunctionType,
    NumericType,
    RecordType,
    StringType,
    UnitType,
)
from cicada.domain.datetime import Datetime
from cicada.domain.triggers import CommitTrigger, GitSha
from cicada.parse.tokenize import tokenize
from test.ast.common import build_trigger


def test_basic_function_call_is_valid() -> None:
    tree = parse_and_analyze("shell echo hi")

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


def test_unknown_variable_causes_error() -> None:
    msg = "Variable `unknown` is not defined"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("unknown")


def test_undefined_variable_causes_error() -> None:
    with pytest.raises(AstError, match="Variable `x` is not defined"):
        parse_and_analyze("let y = x")


def test_boolean_not_on_non_bool_fails() -> None:
    msg = "Cannot use `not` operator with non-boolean value"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("let x = not 1")


def test_negation_on_non_numeric_fails() -> None:
    msg = "Cannot use `-` operator with non-numeric value"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("let x = - false")


@pytest.mark.xfail(reason="Need a way to create non-constexpr values in DSL")
def test_on_statement_where_clause_must_be_const_expr() -> None:
    msg = "`where` clause must be a constant expression"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(
            "let x = false\non abc where x", build_trigger("abc")
        )


def test_on_statement_where_clause_must_be_bool() -> None:
    msg = "`where` clause must be a boolean type"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("on abc where 123", build_trigger("abc"))


def test_lhs_of_member_expr_cannot_be_identifier() -> None:
    msg = "Member `a` does not exist on `x`"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("let x = 123\nlet y = x.a")


def test_record_lhs_of_member_expr_must_exist() -> None:
    msg = "Member `doesnt_exist` does not exist on `event`"

    trigger = build_trigger("a")

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("let x = event.doesnt_exist", trigger)


def test_binary_exprs_must_be_of_same_type() -> None:
    msg = "Expression of type `bool` cannot be used with type `number`"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("let x = 1 + true")


def test_binary_expr_must_be_an_allowed_type() -> None:
    msg = "Expected type `number`, got type `bool` instead"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("let x = true * true")


def test_binary_expr_error_message_with_multiple_allowed_types() -> None:
    msg = "Expected type `number`, or `string`, got type `bool` instead"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("let x = true + true")


def test_constexpr_propagation() -> None:
    tree = parse_and_analyze(
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
            LetExpression(
                name="a", expr=Expression(is_constexpr=True), is_constexpr=True
            ),
            LetExpression(
                name="b", expr=Expression(is_constexpr=True), is_constexpr=True
            ),
            LetExpression(
                name="c", expr=Expression(is_constexpr=True), is_constexpr=True
            ),
            LetExpression(
                name="d", expr=Expression(is_constexpr=True), is_constexpr=True
            ),
        ]:
            return

    pytest.fail(f"tree does not match: {tree}")


def test_binary_expr_types_match_operator() -> None:
    tree = parse_and_analyze(
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


def test_cannot_use_non_constexpr_stmt_before_on_stmt() -> None:
    msg = "Cannot use `on` statement after a function call"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("echo hi\non x")


def test_cannot_use_non_constexpr_stmt_before_run_on_stmt() -> None:
    msg = "Cannot use `run_on` statement after a function call"

    code = """\
echo hi
run_on image alpine
"""

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code)


def test_cannot_use_multiple_on_stmts() -> None:
    msg = "Cannot use multiple `on` statements in a single file"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("on a\non b", build_trigger("a"))


def test_cannot_use_multiple_run_on_stmts() -> None:
    msg = "Cannot use multiple `run_on` statements in a single file"

    code = """\
run_on image alpine
run_on image ubuntu
"""

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code)


def test_variable_name_cannot_by_reserved_name() -> None:
    for name in RESERVED_NAMES:
        msg = f"Name `{name}` is reserved"

        with pytest.raises(AstError, match=msg):
            parse_and_analyze(f"let {name} = 123")


def test_type_checking_of_event_triggers() -> None:
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
    tree.accept(visitor)

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


def test_on_statement_requires_trigger() -> None:
    msg = "Cannot use `on` statement when trigger is not defined"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("on git.push")


def test_environment_variable_semantics() -> None:
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
    tree.accept(visitor)

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


def test_ast_error_with_filename() -> None:
    err = AstError("Test", LineInfo(1, 2, 1, 2))

    assert str(err) == "<unknown>:1:2: Test"

    err.filename = "file.ci"

    assert str(err) == "file.ci:1:2: Test"


def test_if_expr_condition_must_be_bool_like() -> None:
    msg = "Type `record` cannot be converted to bool"

    # TODO: replace "event" with different type once more exprs types are added
    code = """\
if event:
    echo nope
"""

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code, trigger=build_trigger("xyz"))


@pytest.mark.xfail()
def test_if_expr_must_have_body() -> None:
    code = """\
if true:
    # comment
"""

    with pytest.raises(AstError, match="If expression must have body"):
        parse_and_analyze(code)


def test_if_expr_creates_its_own_scope() -> None:
    code = """\
if true:
    let x = 1

echo (x)
"""

    msg = "`x` is not defined"

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_single_func_expr_in_if_failing() -> None:
    code = """\
if true:
    echo hi
"""

    parse_and_analyze(code)


def test_shell_function_args_are_not_stringifyable() -> None:
    code = """\
let x =
    echo hi

echo (x)
"""

    msg = "Cannot convert type `record` to `string`"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code)


def test_error_on_reassigning_immutable_variable() -> None:
    code = """\
let x = 123

x = 456
"""

    msg = "Cannot assign to immutable variable `x` (are you forgetting `mut`?)"

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_cannot_assign_to_non_identifiers() -> None:
    code = "123 = 456"

    msg = "You can only assign to variables"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code)


def test_error_message_when_reassigning_improper_type() -> None:
    code = """\
let mut x = 123

x = "hello world"
"""

    msg = "`string` cannot be assigned to type `number`"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code)


def test_non_string_types_allowed_in_interpolated_strings() -> None:
    # TODO: fix newline being required here
    code = "echo abc(123)xyz\n"

    tree = parse_and_analyze(code)

    match tree.exprs[0]:
        case FunctionExpression(
            callee=IdentifierExpression("shell"),
            args=[
                StringExpression("echo"),
                BinaryExpression(
                    StringExpression("abc"),
                    BinaryOperator.ADD,
                    BinaryExpression(
                        ToStringExpression(
                            ParenthesisExpression(NumericExpression(123))
                        ),
                        BinaryOperator.ADD,
                        StringExpression("xyz"),
                    ),
                ),
            ],
        ):
            return

    pytest.fail(f"tree does not match: {tree.exprs[0]}")


def test_error_message_when_assigning_non_string_value_to_env() -> None:
    code = "env.ABC = 123"

    msg = "You can only assign strings to env vars"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code, trigger=build_trigger("xyz"))


def test_error_message_when_assigning_to_nonexistent_member_expr() -> None:
    code = "unknown.variable = 123"

    msg = "Variable `unknown` is not defined"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code)


def test_cannot_reassign_event_exprs() -> None:
    code = "event.ABC = 123"

    msg = "Cannot reassign `event` because it is immutable"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze(code, trigger=build_trigger("xyz"))


def test_check_return_types_of_builtin_funcs() -> None:
    code = """\
print("hello world")
hashOf("some_file")
"""

    tree = parse_and_analyze(code)

    match tree.exprs:
        case [
            FunctionExpression(
                callee=IdentifierExpression("print"), type=UnitType()
            ),
            FunctionExpression(
                callee=IdentifierExpression("hashOf"), type=StringType()
            ),
        ]:
            return

    pytest.fail(f"tree does not match: {tree}")


def test_hash_of_requires_at_least_one_arg() -> None:
    msg = "Function `hashOf` takes at least 1 argument but was called with 0 arguments"  # noqa: E501

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze("hashOf()")


def test_hash_of_requires_string_only_args() -> None:
    msg = "Expected type `string`, got type `number` instead"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("hashOf(1)")


def test_proper_cache_stmt_is_valid() -> None:
    parse_and_analyze('cache file using "key"')


def test_cache_key_must_be_string() -> None:
    msg = "Expected `string` type, got type `number`"

    with pytest.raises(AstError, match=msg):
        parse_and_analyze("cache file using 123")


def test_only_one_cache_stmt_allowed_per_file() -> None:
    code = """\
cache x using "abc"
cache y using "xyz"
"""

    msg = "Cannot have multiple `cache` statements"

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_only_one_title_stmt_allowed_per_file() -> None:
    code = """\
title A
title B
"""

    msg = "Cannot have multiple `title` statements in a single file"

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_parse_valid_title_stmt() -> None:
    tree = parse_and_analyze("title Hello world")

    match tree.exprs[0]:
        case TitleStatement(
            parts=[StringExpression("Hello"), StringExpression("world")]
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


def test_basic_member_functions() -> None:
    code = """\
let x = "abc"
let y = x.starts_with("abc")
"""

    tree = parse_and_analyze(code)

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


def test_member_functions_on_member_exprs() -> None:
    trigger = build_trigger("x")

    code = """\
let x = event.type.starts_with("x")
"""

    tree = parse_and_analyze(code, trigger)

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


def test_starts_with_must_have_one_arg() -> None:
    msg = "Function `starts_with` takes 1 argument but was called with 0 arguments"  # noqa: E501

    code = """\
let x = ""
let x = x.starts_with()
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)

    code = """\
let x = ""
let x = x.starts_with("y", "z")
"""

    msg = "Function `starts_with` takes 1 argument but was called with 2 arguments"  # noqa: E501

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_starts_with_must_have_string_arg() -> None:
    msg = "Expected type `string`, got type `number` instead"

    code = """\
let x = ""
let x = x.starts_with(1)
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_func_def_is_typed_correctly() -> None:
    code = """\
fn f():
  echo hi
"""

    tree = parse_and_analyze(code)

    match tree.exprs[0]:
        case FunctionDefStatement(
            body=BlockExpression(exprs=[FunctionExpression()]),
            type=FunctionType(arg_types=[], rtype=UnitType()),
        ):
            return

    pytest.fail(f"tree does not match: {tree}")


def test_cannot_call_no_arg_func_with_args() -> None:
    msg = "Function `f` takes 0 arguments but was called with 1 argument"

    code = """\
fn f():
    echo hi

f(123)
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_cannot_call_single_arg_func_with_no_args() -> None:
    msg = "Function `f` takes 1 argument but was called with 0 arguments"

    code = """\
fn f(x):
    echo hi

f()
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_cannot_have_func_with_duplicate_argument_names() -> None:
    msg = "Argument `x` already exists"

    code = """\
fn f(x, x):
    echo hi
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_must_call_user_defined_functions_with_proper_types() -> None:
    msg = "Expected type `string`, got type `number` instead"

    code = """\
fn f(x):
    echo hi

f(1)
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_function_return_type_must_match_block_rtype() -> None:
    msg = "Expected type `number`, got type `string` instead"

    code = """\
fn f() -> number:
    "not a number"
"""

    with pytest.raises(AstError, match=re.escape(msg)):
        parse_and_analyze(code)


def test_body_rtype_ignored_when_function_rtype_is_unit_type() -> None:
    # TODO: if explicit () unit type is used then emit an error

    code = """\
fn f():
    echo not unit type but thats ok
"""

    parse_and_analyze(code)


def test_access_shell_function_record_fields() -> None:
    code = """\
let cmd =
    echo hi

let a = cmd.exit_code
let b = cmd.stdout
let b = cmd.stderr
"""

    tree = parse_and_analyze(code)

    match tree.exprs[0]:
        case LetExpression(
            "cmd",
            expr=BlockExpression(
                exprs=[FunctionExpression(type=CommandType())]
            ),
        ):
            return

    pytest.fail(f"tree does not match: {tree}")
