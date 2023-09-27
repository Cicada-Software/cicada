import re

import pytest

from cicada.ast.generate import AstError, generate_ast_tree
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanExpression,
    CacheStatement,
    FileNode,
    FunctionDefStatement,
    FunctionExpression,
    IdentifierExpression,
    IfExpression,
    LetExpression,
    LineInfo,
    MemberExpression,
    NumericExpression,
    OnStatement,
    ParenthesisExpression,
    RunOnStatement,
    RunType,
    StringExpression,
    TitleStatement,
    ToStringExpression,
)
from cicada.ast.types import (
    FunctionType,
    NumericType,
    StringType,
    UnitType,
    UnknownType,
)
from cicada.parse.tokenize import tokenize


def test_generate_empty_token_stream_returns_empty_file() -> None:
    assert generate_ast_tree([]) == FileNode([])


def test_generate_function_expression() -> None:
    tree = generate_ast_tree(tokenize("shell x y z"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    IdentifierExpression("shell"),
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
    tree = generate_ast_tree(tokenize("shell x\nshell y"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    IdentifierExpression("shell"),
                    [StringExpression("x")],
                    info=LineInfo(line=1, column_start=1),
                    type=UnknownType(),
                ),
                FunctionExpression(
                    IdentifierExpression("shell"),
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
                    IdentifierExpression("shell"),
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
                    is_mutable=False,
                    info=LineInfo(line=1, column_start=1),
                    type=NumericType(),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_mutable_let_expression() -> None:
    tree = generate_ast_tree(tokenize("let mut x = 1"))

    match tree:
        case FileNode(
            [
                LetExpression(
                    "x",
                    NumericExpression(1),
                    is_mutable=True,
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
    tree = generate_ast_tree(tokenize("shell x --help"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    IdentifierExpression("shell"),
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
    # Fix newline being needed here
    tree = generate_ast_tree(tokenize("shell (x) lhs(x) (x)rhs\n"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    IdentifierExpression("shell"),
                    [
                        ToStringExpression(
                            ParenthesisExpression(IdentifierExpression()),
                        ),
                        BinaryExpression(
                            StringExpression("lhs"),
                            BinaryOperator.ADD,
                            ToStringExpression(
                                ParenthesisExpression(IdentifierExpression()),
                            ),
                        ),
                        BinaryExpression(
                            ToStringExpression(
                                ParenthesisExpression(IdentifierExpression()),
                            ),
                            BinaryOperator.ADD,
                            StringExpression("rhs"),
                        ),
                    ],
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_func_expr_with_parens2() -> None:
    tree = generate_ast_tree(tokenize("shell arg1 (arg2) arg3"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    IdentifierExpression("shell"),
                    [
                        StringExpression("arg1"),
                        ToStringExpression(
                            ParenthesisExpression(
                                IdentifierExpression("arg2"),
                            ),
                        ),
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


def test_suggestion_is_given_when_identifier_is_used_like_a_function() -> None:
    expected = "Unexpected identifier `install`. Did you mean `shell npm install ...`?"  # noqa: E501

    with pytest.raises(AstError, match=re.escape(expected)):
        generate_ast_tree(tokenize("npm install"))


def test_suggestion_is_given_when_identifier_is_similar_to_keyword() -> None:
    expected = "Unexpected identifier `image`. Did you mean `run_on image ...`?"  # noqa: E501

    with pytest.raises(AstError, match=re.escape(expected)):
        generate_ast_tree(tokenize("runs_on image alpine"))


def test_no_arg_func_calls_skipping_newline() -> None:
    code = """\
shell x
shell
shell y
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    IdentifierExpression("shell"), [StringExpression("x")]
                ),
                FunctionExpression(IdentifierExpression("shell"), []),
                FunctionExpression(
                    IdentifierExpression("shell"), [StringExpression("y")]
                ),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_basic_if_statement() -> None:
    code = """\
if true:
    let x = 1
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                IfExpression(
                    condition=BooleanExpression(True),
                    body=BlockExpression(
                        [LetExpression("x", NumericExpression(1))]
                    ),
                )
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_require_colon_after_if_expr_cond() -> None:
    with pytest.raises(AstError, match="Expected `:`"):
        generate_ast_tree(tokenize("if x x"))


def test_require_newline_after_if_expr_cond() -> None:
    with pytest.raises(AstError, match="Expected newline"):
        generate_ast_tree(tokenize("if x: "))


def test_require_whitespace_after_if_expr_cond() -> None:
    with pytest.raises(AstError, match="Expected indentation"):
        generate_ast_tree(tokenize("if x:\nx"))


def test_expr_statements() -> None:
    code = """\
123
"abc"

if true:
    321
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                NumericExpression(123),
                StringExpression("abc"),
                IfExpression(
                    condition=BooleanExpression(True),
                    body=BlockExpression([NumericExpression(321)]),
                ),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_nested_let_exprs() -> None:
    tree = generate_ast_tree(tokenize("let x = let y = 1"))

    match tree:
        case FileNode(
            [
                LetExpression("x", LetExpression("y", NumericExpression(1))),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_interpolated_function_arg_doesnt_gobble_newline() -> None:
    tree = generate_ast_tree(tokenize("shell (x)\nshell (y)"))

    match tree:
        case FileNode(
            [
                FunctionExpression(
                    IdentifierExpression("shell"),
                    [
                        ToStringExpression(
                            ParenthesisExpression(IdentifierExpression("x")),
                        )
                    ],
                ),
                FunctionExpression(
                    IdentifierExpression("shell"),
                    [
                        ToStringExpression(
                            ParenthesisExpression(IdentifierExpression("y"))
                        )
                    ],
                ),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_allow_if_expr_in_let_expr() -> None:
    # TODO: this will fail once I tighten up if semantics, but the thing being
    # tested is that the AST generator doesnt fail.

    code = """\
let x = if true:
    1

shell
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                LetExpression(
                    "x",
                    IfExpression(
                        condition=BooleanExpression(True),
                        body=BlockExpression([NumericExpression(1)]),
                    ),
                ),
                FunctionExpression(IdentifierExpression("shell"), []),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_allow_let_expr_value_to_be_on_newline() -> None:
    code = """\
let x =
    1
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                LetExpression("x", BlockExpression([NumericExpression(1)])),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_nested_blocks_dont_interfere_with_trailing_nodes() -> None:
    code = """\
let x =
  if true:
      1

shell
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                LetExpression(
                    "x",
                    BlockExpression(
                        [
                            IfExpression(
                                condition=BooleanExpression(True),
                                body=BlockExpression([NumericExpression(1)]),
                            ),
                        ],
                    ),
                ),
                FunctionExpression(IdentifierExpression("shell"), []),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_blocks_must_have_consistent_indentation() -> None:
    code = """\
if true:
  if true:
 if true:
  1
"""

    msg = "Indentation cannot be smaller than previous block"

    with pytest.raises(AstError, match=msg):
        generate_ast_tree(tokenize(code))


def test_many_nested_blocks_in_block() -> None:
    code = """\
if true:
  if true:
    1
  if true:
    1
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                IfExpression(
                    condition=BooleanExpression(True),
                    body=BlockExpression(
                        [
                            IfExpression(
                                condition=BooleanExpression(True),
                                body=BlockExpression([NumericExpression(1)]),
                            ),
                            IfExpression(
                                condition=BooleanExpression(True),
                                body=BlockExpression([NumericExpression(1)]),
                            ),
                        ],
                    ),
                ),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_stray_indented_whitespace_is_ok() -> None:
    code = """\
if true:
  if true:
    1
    
  if true:
    1
"""

    tree = generate_ast_tree(tokenize(code))

    match tree:
        case FileNode(
            [
                IfExpression(
                    condition=BooleanExpression(True),
                    body=BlockExpression(
                        [
                            IfExpression(
                                condition=BooleanExpression(True),
                                body=BlockExpression([NumericExpression(1)]),
                            ),
                            IfExpression(
                                condition=BooleanExpression(True),
                                body=BlockExpression([NumericExpression(1)]),
                            ),
                        ],
                    ),
                ),
            ]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_blocks_cannot_mix_tabs_and_spaces() -> None:
    code = """\
if true:
\t 1

---

if true:
\tif true:
  1

---

if true:
 if true:
\t\t1
"""

    tests = code.split("---")

    for test in tests:
        with pytest.raises(AstError, match="Cannot mix spaces and tabs"):
            generate_ast_tree(tokenize(test))


def test_stray_dangling_tokens_give_useful_error_message() -> None:
    code = "let x = 0.abc"

    with pytest.raises(AstError, match="unexpected token"):
        generate_ast_tree(tokenize(code))


def test_error_on_overindented_code() -> None:
    code = """\
if true:
  echo hello
      echo world
"""

    with pytest.raises(AstError, match="Unexpected indentation"):
        generate_ast_tree(tokenize(code))


def test_let_identifier_cannot_be_named_mut() -> None:
    code = "let mut = 123"

    with pytest.raises(AstError, match="expected identifier"):
        generate_ast_tree(tokenize(code))


def test_let_identifier_cannot_be_a_keyword() -> None:
    code = "let if = 123"

    with pytest.raises(AstError, match="cannot use keyword"):
        generate_ast_tree(tokenize(code))


def test_let_name_must_be_identifier() -> None:
    code = 'let "x" = 123'

    with pytest.raises(AstError, match="expected identifier"):
        generate_ast_tree(tokenize(code))


def test_show_error_when_expression_is_expected() -> None:
    code = "if ="

    with pytest.raises(AstError, match="expected an expression, got `=`"):
        generate_ast_tree(tokenize(code))


def test_generate_run_on_stmt_with_image() -> None:
    images = (
        "hello_world",
        "alpine:3.18",
        "alpine:3",
        "docker.io/alpine",
        "python:3.11.3-alpine3.18",
    )

    for image in images:
        tree = generate_ast_tree(tokenize(f"run_on image {image}"))

        match tree.exprs[0]:
            case RunOnStatement(RunType.IMAGE, value) if value == image:
                continue

        pytest.fail(f"Tree did not match:\n{tree}")


def test_generate_run_on_stmt_with_self_hosted() -> None:
    tree = generate_ast_tree(tokenize("run_on self_hosted"))

    match tree.exprs[0]:
        case RunOnStatement(RunType.SELF_HOSTED, value=""):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_run_on_must_have_content_after_space() -> None:
    code = "run_on image "

    with pytest.raises(AstError, match="expected token after ` `"):
        generate_ast_tree(tokenize(code))


def test_run_on_must_have_space_after_run_type() -> None:
    code = "run_on image"

    with pytest.raises(AstError, match="expected whitespace"):
        generate_ast_tree(tokenize(code))


def test_run_on_must_have_valid_type() -> None:
    code = "run_on invalid"

    with pytest.raises(
        AstError,
        match="invalid `run_on` type `invalid`. Did you mean `image`?",
    ):
        generate_ast_tree(tokenize(code))


def test_run_on_suggestion_for_self_host_like_types() -> None:
    tests = (
        "self host",
        "self-host",
        "self-hosted",
        "self_host",
        "SELF_HOSTED",
    )

    for test in tests:
        with pytest.raises(AstError, match="Did you mean `self_hosted`?"):
            generate_ast_tree(tokenize(f"run_on {test}"))


def test_parse_c_style_function_call() -> None:
    code = "print(123)"
    tree = generate_ast_tree(tokenize(code))

    match tree.exprs[0]:
        case FunctionExpression(
            callee=IdentifierExpression("print"),
            args=[NumericExpression()],
            is_shell_mode=False,
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_parse_c_style_function_call_with_no_args() -> None:
    code = "print()"
    tree = generate_ast_tree(tokenize(code))

    match tree.exprs[0]:
        case FunctionExpression(
            callee=IdentifierExpression("print"),
            args=[],
            is_shell_mode=False,
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_parse_c_style_function_call_with_many_args() -> None:
    code = 'print("hello", "world")'
    tree = generate_ast_tree(tokenize(code))

    match tree.exprs[0]:
        case FunctionExpression(
            callee=IdentifierExpression("print"),
            args=[StringExpression("hello"), StringExpression("world")],
            is_shell_mode=False,
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree}")


def test_parse_cache_stmt() -> None:
    code = 'cache file using "xyz"\n'
    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case CacheStatement(
            files=[StringExpression("file")],
            using=StringExpression("xyz"),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_error_messages_for_invalid_cache_stmts() -> None:
    invalid_cache = "Invalid `cache` statement"

    tests = {
        "cache": invalid_cache,
        "cache ": invalid_cache,
        "cache x ": invalid_cache,
        "cache x x": "expected `using`",
        "cache x using ": invalid_cache,
    }

    for code, expected in tests.items():
        with pytest.raises(AstError, match=re.escape(expected)):
            generate_ast_tree(tokenize(code))


def test_generate_title() -> None:
    code = "title Hello world!"

    tree = generate_ast_tree(tokenize(code))

    match tree.exprs[0]:
        case TitleStatement(
            parts=[StringExpression("Hello"), StringExpression("world!")]
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_title_cannot_be_empty() -> None:
    code = "title "

    msg = "Expected expression after `title`"

    with pytest.raises(AstError, match=re.escape(msg)):
        generate_ast_tree(tokenize(code))


def test_parse_c_func_expr_in_binary_expr() -> None:
    code = "let x = f() or g()"
    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case LetExpression(
            "x",
            BinaryExpression(
                lhs=FunctionExpression(IdentifierExpression("f")),
                oper=BinaryOperator.OR,
                rhs=FunctionExpression(IdentifierExpression("g")),
            ),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_in_binary_oper() -> None:
    code = 'let x = "a" in "abc"'
    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case LetExpression(
            "x",
            BinaryExpression(
                lhs=StringExpression("a"),
                oper=BinaryOperator.IN,
                rhs=StringExpression("abc"),
            ),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_not_in_binary_oper() -> None:
    code = 'let x = "a" not in "abc"'
    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case LetExpression(
            "x",
            BinaryExpression(
                lhs=StringExpression("a"),
                oper=BinaryOperator.NOT_IN,
                rhs=StringExpression("abc"),
            ),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_in_must_follow_not_in_binary_expr_context() -> None:
    code = 'let x = "a" not + "abc"'

    with pytest.raises(AstError, match="expected `in`"):
        generate_ast_tree(tokenize(code))


def test_is_not_binary_oper() -> None:
    code = "let x = 1 is not 2"
    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case LetExpression(
            "x",
            BinaryExpression(
                lhs=NumericExpression(1),
                oper=BinaryOperator.IS_NOT,
                rhs=NumericExpression(2),
            ),
        ):
            # TODO: bug in mypy
            return  # type: ignore[unreachable]

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_parse_void_no_arg_function() -> None:
    code = """\
fn f():
  echo hi
"""

    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case FunctionDefStatement(
            name="f",
            arg_names=[],
            type=FunctionType([], rtype=UnitType()),
            body=BlockExpression(
                [
                    FunctionExpression(
                        callee=IdentifierExpression("shell"),
                        args=[
                            StringExpression("echo"),
                            StringExpression("hi"),
                        ],
                    ),
                ],
            ),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_parse_void_single_arg_function() -> None:
    code = """\
fn say_hi(x):
  echo hi
"""

    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case FunctionDefStatement(
            name="say_hi",
            arg_names=["x"],
            type=FunctionType([StringType()], rtype=UnitType()),
            body=BlockExpression([FunctionExpression()]),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_parse_void_multi_arg_function() -> None:
    code = """\
fn f(x, y):
  echo hi
"""

    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case FunctionDefStatement(
            name="f",
            arg_names=["x", "y"],
            type=FunctionType(
                [StringType(), StringType()],
                rtype=UnitType(),
            ),
            body=BlockExpression([FunctionExpression()]),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_parse_function_with_return_type() -> None:
    code = """\
fn f() -> string:
  "hello world"
"""

    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case FunctionDefStatement(
            name="f",
            arg_names=[],
            type=FunctionType([], rtype=StringType()),
            body=BlockExpression([StringExpression()]),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_parse_function_with_explicit_unit_rtype() -> None:
    code = """\
fn f() -> ():
  echo hi
"""

    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case FunctionDefStatement(
            name="f",
            arg_names=[],
            type=FunctionType([], rtype=UnitType()),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_parse_function_with_arg_type() -> None:
    code = """\
fn add(x: number, y: number) -> number:
  x + y
"""

    tree = generate_ast_tree(tokenize(code))

    assert tree

    match tree.exprs[0]:
        case FunctionDefStatement(
            name="add",
            arg_names=["x", "y"],
            type=FunctionType(
                [NumericType(), NumericType()],
                rtype=NumericType(),
            ),
        ):
            return

    pytest.fail(f"Tree did not match:\n{tree.exprs[0]}")


def test_invalid_function_defs_are_caught() -> None:
    tests = {
        "fn": "expected token after `fn`",
        "fn fn": "Cannot use keyword `fn` as function name",
        "fn 1": "Expected identifier, got `1` instead",
        "fn f": "expected `(`",
        "fn f+": "expected `(`",
        "fn f(": "expected `)`",
        "fn f(+": "expected `)`",
        "fn f()": "expected `:`",
        "fn f()x": "expected `:`",
        "fn f():": "expected `\\n`",
        "fn f():\n": "Expected whitespace after function definition",
        "fn f():\nx": "Expected whitespace after function definition",
        "fn f(x": "Expected `,` or `)`",
        "fn f(x,": "Expected argument",
        "fn f() -": "expected `->`",
        "fn f() ->": "Expected type",
        "fn f() -> x": "Unknown type `x`",
        "fn f() -> string": "expected `:`",
        "fn f() -> string:": "expected `\\n`",
        "fn f() -> (": "expected `)`",
        "fn f() -> ()": "expected `:`",
        "fn f(x:": "Expected type",
        "fn f(x: number": "Expected `,` or `)`",
    }

    for test, expected in tests.items():
        with pytest.raises(AstError, match=re.escape(expected)):
            generate_ast_tree(tokenize(test))
