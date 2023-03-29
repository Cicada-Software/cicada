import pytest

from cicada.ast.generate import AstError, generate_ast_tree
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BooleanExpression,
    FileNode,
    FunctionExpression,
    IdentifierExpression,
    LetExpression,
    LineInfo,
    MemberExpression,
    NumericExpression,
    OnStatement,
    ParenthesisExpression,
    StringExpression,
)
from cicada.ast.types import NumericType, StringType, UnknownType
from cicada.parse.tokenize import tokenize


def test_generate_empty_token_stream_returns_empty_file() -> None:
    assert generate_ast_tree([]) == FileNode([])


def test_generate_function_expression() -> None:
    tree = generate_ast_tree(tokenize("f x y z"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    "f",
                    [
                        StringExpression("x"),
                        StringExpression("y"),
                        StringExpression("z"),
                    ],
                    info=LineInfo(line=1, column_start=1),
                    type=UnknownType(),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_function_expression_splits_on_newlines() -> None:
    tree = generate_ast_tree(tokenize("f x\nf y"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    "f",
                    [StringExpression("x")],
                    info=LineInfo(line=1, column_start=1),
                    type=UnknownType(),
                ),
                FunctionExpression(
                    "f",
                    [StringExpression("y")],
                    info=LineInfo(line=2, column_start=1),
                    type=UnknownType(),
                ),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_shell_alias_function_expression_using() -> None:
    tree = generate_ast_tree(tokenize("echo hi"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    "shell",
                    [
                        StringExpression("echo"),
                        StringExpression("hi"),
                    ],
                    info=LineInfo(line=1, column_start=1),
                    type=UnknownType(),
                ),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_let_expression() -> None:
    tree = generate_ast_tree(tokenize("let x = 1"))

    match tree:
        case FileNode(
            [
                LetExpression(
                    "x",
                    NumericExpression(1),
                    info=LineInfo(line=1, column_start=1),
                    type=NumericType(),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_paren_expression() -> None:
    tree = generate_ast_tree(tokenize("let x = (1)"))

    match tree:
        case FileNode(
            [
                LetExpression(
                    "x",
                    ParenthesisExpression(NumericExpression(1)),
                    info=LineInfo(line=1, column_start=1),
                    type=NumericType(),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_bool_expr() -> None:
    tree = generate_ast_tree(tokenize("let x = true"))

    match tree:
        case FileNode([LetExpression("x", BooleanExpression(value=True))]):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_catch_missing_closing_paren() -> None:
    with pytest.raises(AstError, match="expected token after `1`"):
        generate_ast_tree(tokenize("let x = (1"))

    with pytest.raises(AstError, match=r"expected `\)`"):
        generate_ast_tree(tokenize("let x = (1 x"))


def test_generate_alternate_let_expression() -> None:
    tree = generate_ast_tree(tokenize('let s = "abc"'))

    match tree:
        case FileNode(
            [
                LetExpression(
                    "s",
                    StringExpression("abc"),
                    info=LineInfo(line=1, column_start=1),
                    type=StringType(),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_on_statement() -> None:
    tree = generate_ast_tree(tokenize("on some_event"))

    match tree:
        case FileNode(
            [
                OnStatement(
                    "some_event",
                    info=LineInfo(line=1, column_start=1),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_on_statement_with_where_clause() -> None:
    tree = generate_ast_tree(tokenize("on some_event where true"))

    match tree:
        case FileNode(
            [
                OnStatement(
                    "some_event",
                    info=LineInfo(line=1, column_start=1),
                    where=BooleanExpression(True),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_invalid_let_exprs_are_caught() -> None:
    with pytest.raises(AstError, match="expected token after `let`"):
        generate_ast_tree(tokenize("let"))

    with pytest.raises(AstError, match="expected token after `x`"):
        generate_ast_tree(tokenize("let x"))

    with pytest.raises(AstError, match="expected token after `=`"):
        generate_ast_tree(tokenize("let x ="))

    with pytest.raises(AstError, match="expected `=`"):
        generate_ast_tree(tokenize("let x 123"))


def test_invalid_on_stmt_is_caught() -> None:
    with pytest.raises(AstError, match="expected token after `on`"):
        generate_ast_tree(tokenize("on"))


def test_parse_identifier_with_invalid_dot_placement_fails() -> None:
    tests = {
        "x.": "<unknown>:1:2: Unexpected `.` in token",
        ".x": "<unknown>:1:1: Unexpected `.` in token",
        "x..y": "<unknown>:1:2: Unexpected `.` in token",
        "a.b..c.d": "<unknown>:1:2: Unexpected `.` in token",
    }

    for test, expected in tests.items():
        with pytest.raises(AstError, match=expected):
            generate_ast_tree(tokenize(test))


def test_parse_identifier_expr() -> None:
    tree = generate_ast_tree(tokenize("let x = y"))

    match tree.exprs[0]:
        case LetExpression(
            "x",
            IdentifierExpression(
                "y",
                info=LineInfo(line=1, column_start=9, column_end=9),
                type=UnknownType(),
            ),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_parse_member_expr() -> None:
    tree = generate_ast_tree(tokenize("a.b"))

    match tree.exprs[0]:
        case MemberExpression(
            IdentifierExpression(
                "a",
                info=LineInfo(line=1, column_start=1, column_end=1),
                type=UnknownType(),
            ),
            name="b",
            info=LineInfo(line=1, column_start=1, column_end=3),
            type=UnknownType(),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_parse_nested_member_expr() -> None:
    tree = generate_ast_tree(tokenize("a.b.c"))

    match tree.exprs[0]:
        case MemberExpression(
            MemberExpression(
                IdentifierExpression(
                    "a",
                    info=LineInfo(line=1, column_start=1, column_end=1),
                    type=UnknownType(),
                ),
                name="b",
            ),
            name="c",
            info=LineInfo(line=1, column_start=1, column_end=5),
            type=UnknownType(),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_function_expression_group_contiguous_chars() -> None:
    tree = generate_ast_tree(tokenize("f x --help"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    "f",
                    [
                        StringExpression("x"),
                        StringExpression("--help"),
                    ],
                    info=LineInfo(line=1, column_start=1),
                    type=UnknownType(),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_func_expr_with_parens() -> None:
    tree = generate_ast_tree(tokenize("f (x)"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    "f",
                    [ParenthesisExpression(IdentifierExpression())],
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_func_expr_with_parens2() -> None:
    tree = generate_ast_tree(tokenize("f arg1 (arg2) arg3"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    "f",
                    [
                        StringExpression("arg1"),
                        ParenthesisExpression(IdentifierExpression("arg2")),
                        StringExpression("arg3"),
                    ],
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


# TODO: test unary exprs
def test_generate_binary_expr() -> None:
    tree = generate_ast_tree(tokenize("let x = 1 + 2"))

    match tree:
        case FileNode(
            [
                LetExpression(
                    expr=BinaryExpression(
                        lhs=NumericExpression(1),
                        oper=BinaryOperator.ADD,
                        rhs=NumericExpression(2),
                    )
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_nested_binary_expr() -> None:
    tree = generate_ast_tree(tokenize("let x = 1 + 2 + 3"))

    match tree:
        case FileNode(
            [
                LetExpression(
                    expr=BinaryExpression(
                        lhs=BinaryExpression(
                            lhs=NumericExpression(1),
                            oper=BinaryOperator.ADD,
                            rhs=NumericExpression(2),
                        ),
                        oper=BinaryOperator.ADD,
                        rhs=NumericExpression(3),
                    )
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_nested_binary_expr_respects_oop() -> None:
    tree = generate_ast_tree(tokenize("let x = 1 + 2 * 3"))

    match tree:
        case FileNode(
            [
                LetExpression(
                    expr=BinaryExpression(
                        lhs=NumericExpression(1),
                        oper=BinaryOperator.ADD,
                        rhs=BinaryExpression(
                            lhs=NumericExpression(2),
                            oper=BinaryOperator.MULTIPLY,
                            rhs=NumericExpression(3),
                        ),
                    )
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_very_nested_binary_expr() -> None:
    tree = generate_ast_tree(tokenize("let x = 1 + 2 * 3 * 4"))

    match tree:
        case FileNode(
            [
                LetExpression(
                    expr=BinaryExpression(
                        lhs=NumericExpression(1),
                        oper=BinaryOperator.ADD,
                        rhs=BinaryExpression(
                            lhs=BinaryExpression(
                                lhs=NumericExpression(2),
                                oper=BinaryOperator.MULTIPLY,
                                rhs=NumericExpression(3),
                            ),
                            oper=BinaryOperator.MULTIPLY,
                            rhs=NumericExpression(4),
                        ),
                    )
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_binary_expr_with_parenthesis() -> None:
    tree = generate_ast_tree(tokenize("let x = (1 + 2)"))

    match tree:
        case FileNode(
            [
                LetExpression(
                    expr=ParenthesisExpression(
                        BinaryExpression(
                            lhs=NumericExpression(1),
                            oper=BinaryOperator.ADD,
                            rhs=NumericExpression(2),
                        )
                    )
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_disallow_multiple_exprs_on_same_line() -> None:
    with pytest.raises(AstError, match="Expected newline"):
        generate_ast_tree(tokenize("on x 1"))

    with pytest.raises(AstError, match="Expected newline"):
        generate_ast_tree(tokenize("let x = 1 2"))


def test_generate_nice_error_message_for_invalid_equal_token() -> None:
    msg = "Unexpected operator `=`, did you mean `is` instead?"

    with pytest.raises(AstError, match=msg):
        generate_ast_tree(tokenize("let x = 123 = 456"))


def test_no_arg_func_calls_skipping_newline() -> None:
    code = """\
f x
f
f y
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                FunctionExpression("f", [StringExpression("x")]),
                FunctionExpression("f", []),
                FunctionExpression("f", [StringExpression("y")]),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")
