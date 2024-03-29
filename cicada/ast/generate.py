import re
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from enum import Enum
from itertools import count, groupby
from pathlib import Path
from types import UnionType as _UnionType
from typing import NoReturn, Self, cast

from cicada.ast.common import pluralize
from cicada.ast.types import FunctionType, StringType, Type, UnitType, UnknownType, string_to_type
from cicada.parse.token import (
    AtToken,
    BooleanLiteralToken,
    BreakToken,
    CacheToken,
    CloseBracketToken,
    CloseParenToken,
    ColonToken,
    CommaToken,
    CommentToken,
    ContinueToken,
    DanglingToken,
    ElifToken,
    ElseToken,
    EqualToken,
    FloatLiteralToken,
    ForToken,
    FunctionToken,
    GreaterThanToken,
    IdentifierToken,
    IfToken,
    ImportToken,
    IntegerLiteralToken,
    InToken,
    KeywordToken,
    LetToken,
    MinusToken,
    MutToken,
    NewlineToken,
    NotToken,
    OnToken,
    OpenBracketToken,
    OpenParenToken,
    RunOnToken,
    SlashToken,
    StringLiteralToken,
    TitleToken,
    Token,
    UsingToken,
    WhereToken,
    WhiteSpaceToken,
)

from .nodes import (
    TOKEN_TO_BINARY_OPER,
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanExpression,
    BreakStatement,
    CacheStatement,
    ContinueStatement,
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
    Node,
    NumericExpression,
    OnStatement,
    ParenthesisExpression,
    RunOnStatement,
    RunType,
    ShellEscapeExpression,
    StringExpression,
    TitleStatement,
    ToStringExpression,
    UnaryExpression,
    UnaryOperator,
)

SHELL_ALIASES = frozenset(
    [
        "cd",
        "cp",
        "echo",
        "git",
        "ls",
        "make",
        "mkdir",
        "rm",
    ]
)


class AstError(ValueError):
    filename: str | None
    line: int
    column: int
    msg: str

    def __init__(self, msg: str, info: Token | LineInfo | Node) -> None:
        info = info if isinstance(info, Token | LineInfo) else info.info

        self.msg = msg
        self.line = info.line
        self.column = info.column_start
        self.filename = None

        super().__init__(str(self))

    @classmethod
    def expected_token(cls, *, last: Token) -> Self:
        return cls(f"Expected token after `{last.content}`", last)

    @classmethod
    def unexpected_token(cls, token: Token, *, expected: str = "") -> Self:
        if expected:
            return cls(f"Expected `{expected}`", token)

        return cls(f"Unexpected token `{token.content}`", token)

    @classmethod
    def incorrect_arg_count(
        cls,
        *,
        func_name: str,
        expected: int,
        got: int,
        info: Token | LineInfo | Node,
        at_least: bool = False,
    ) -> Self:
        tmp1 = f"{expected} {pluralize('argument', expected)}"
        tmp2 = f"{got} {pluralize('argument', got)}"

        condition = "at least " if at_least else ""

        msg = f"Function `{func_name}` takes {condition}{tmp1} but was called with {tmp2}"

        return cls(msg, info)

    def __str__(self) -> str:
        parts = [
            self.filename or "<unknown>",
            self.line,
            self.column,
            f" {self.msg}",
        ]

        return ":".join(str(x) for x in parts)


class IndentStyle(Enum):
    UNKNOWN = None
    SPACE = " "
    TAB = "\t"


class ParserState:
    tokens: list[Token]

    _current_index: int

    _current_indent_level: int
    _indent_style: IndentStyle

    _loop_depth: int

    def __init__(self, tokens: Sequence[Token]) -> None:
        self.tokens = list(tokens)
        self._current_index = 0
        self._current_indent_level = 0
        self._indent_style = IndentStyle.UNKNOWN
        self._loop_depth = 0

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Token:
        if self._current_index >= len(self.tokens):
            raise StopIteration

        token = self.tokens[self._current_index]
        self._current_index += 1

        return token

    def next_non_whitespace_or_eof(self) -> Token | None:
        try:
            return self.next_non_whitespace()

        except StopIteration:
            return None

    def next_newline_or_eof(self) -> Token | None:
        token = self.next_non_whitespace_or_eof()

        if not token or isinstance(token, NewlineToken):
            return token

        raise AstError("Expected newline", token or self.current_token)

    def next_non_whitespace(self) -> Token:
        token = next(self)

        while isinstance(token, WhiteSpaceToken):
            token = next(self)

        return token

    class Peeker:
        drop_tokens: bool = False

        def drop_peeked_tokens(self) -> None:
            self.drop_tokens = True

    @contextmanager
    def peek(self) -> Iterator[Peeker]:
        """
        When peeking, the parser keeps track of every token that is iterated
        over so that the parser can be reset if needed (for example, checking
        if an optional token follows).

        By default, peeked tokens are kept unless explicitly dropped with the
        `drop_peeked_tokens()` method. `peek()` calls can be nested.
        """

        old_index = self._current_index

        peeker = self.Peeker()
        yield peeker

        if not peeker.drop_tokens:
            self.rewind(old_index)

    def rewind(self, index: int) -> None:
        """
        Rewind the parser to a previous state. If `index` is negative, rewind
        relative to the current position. If `index` is positive, rewind to the
        specified position.
        """

        if index < 0:
            self._current_index += index
        else:
            self._current_index = index

    @property
    def current_token(self) -> Token:
        index = self._current_index - 1 if self._current_index else 0

        return self.tokens[index]

    @contextmanager
    def indent(self, whitespace: WhiteSpaceToken | None) -> Iterator[None]:
        """
        Update the indent level for the duration of this context manager (if
        whitespace is passed, otherwise do nothing). If this function is called
        with an invalid whitespace token (ie, whitespace is under-indented),
        then the function will raise an AstError.
        """

        if not whitespace:
            yield
            return

        whitespace_chars = set(whitespace.content)

        if len(whitespace_chars) > 1:
            raise AstError("Cannot mix spaces and tabs", whitespace)

        indent_style = IndentStyle(whitespace.content[0])

        if self._indent_style == IndentStyle.UNKNOWN:
            self._indent_style = indent_style

        elif indent_style != self._indent_style:
            raise AstError("Cannot mix spaces and tabs", whitespace)

        whitespace_len = len(whitespace.content)

        if whitespace_len <= self._current_indent_level:
            raise AstError(
                "Indentation cannot be smaller than previous block",
                whitespace,
            )

        old_indent_level = self._current_indent_level

        self._current_indent_level = whitespace_len
        yield
        self._current_indent_level = old_indent_level

    def is_over_indented(self, whitespace: WhiteSpaceToken) -> bool:
        """
        Return true if the passed whitespace token is indented further than
        expected, indicating that there is a whitespace mismatch.
        """

        return len(whitespace.content) > self._current_indent_level

    def is_under_indented(self, whitespace: WhiteSpaceToken) -> bool:
        """
        Return true if the passed whitespace is less than the current
        indentation level, indicating that the block is finished, and that
        the whitespace should be handled by the parent block.
        """

        return len(whitespace.content) < self._current_indent_level

    @contextmanager
    def loop_body(self, *, new_scope: bool = False) -> Iterator[None]:
        """
        Increase loop body depth, used for detecting break/continue outside of loop bodies.

        If new_scope is True: store the current depth and reset the loop depth to zero, then
        when the context manager exits, restore the previous scope. This feature is to allow
        detection of break/continue statements hidden by function declarations, since breaking
        out of a loop while inside of a function doesn't make sense.
        """

        if new_scope:
            old = self._loop_depth
            self._loop_depth = 0
            yield
            self._loop_depth = old

        else:
            self._loop_depth += 1
            yield
            self._loop_depth -= 1

    def is_in_loop(self) -> bool:
        return bool(self._loop_depth)


def generate_if_expr(state: ParserState) -> IfExpression:
    start = state.current_token

    state.next_non_whitespace()
    cond = generate_expr(state)
    state.next_non_whitespace()

    if not isinstance(state.current_token, ColonToken):
        raise AstError("Expected `:`", state.current_token)

    next(state)

    if not isinstance(state.current_token, NewlineToken):
        raise AstError("Expected newline", state.current_token)

    next(state)

    expected_whitespace = state.current_token

    if not isinstance(expected_whitespace, WhiteSpaceToken):
        raise AstError("Expected indentation", state.current_token)

    exprs = cast(list[Expression], generate_block(state, expected_whitespace))
    block = BlockExpression.from_exprs(exprs, expected_whitespace)

    elifs = parse_elif_exprs(state, expected_whitespace)
    else_block = parse_else_expr(state, expected_whitespace)

    # TODO: turn into func
    return IfExpression(
        info=LineInfo.from_token(start),
        condition=cond,
        body=block,
        elifs=elifs,
        else_block=else_block,
        type=UnknownType(),
        is_constexpr=False,
    )


def parse_elif_exprs(
    state: ParserState, expected_whitespace: WhiteSpaceToken
) -> list[ElifExpression]:
    elifs: list[ElifExpression] = []

    while True:
        with state.peek() as peeker:
            elif_token = state.next_non_whitespace_or_eof()

            if not isinstance(elif_token, ElifToken):
                break

            peeker.drop_peeked_tokens()

        if not state.next_non_whitespace_or_eof():
            raise AstError("Expected expression", elif_token)

        elif_cond = generate_expr(state)

        colon = state.next_non_whitespace_or_eof()

        if not isinstance(colon, ColonToken):
            raise AstError("Expected `:`", state.current_token)

        newline = next(state, None)

        if not isinstance(newline, NewlineToken):
            raise AstError("Expected newline", newline or colon)

        whitespace = next(state, None)

        if not isinstance(whitespace, WhiteSpaceToken):
            raise AstError("Expected whitespace", whitespace or newline)

        exprs = cast(list[Expression], generate_block(state, expected_whitespace))

        if not exprs:
            raise AstError("Expected expression", state.current_token)

        elif_block = BlockExpression.from_exprs(exprs, expected_whitespace)

        elifs.append(
            ElifExpression(
                info=LineInfo.from_token(elif_token),
                condition=elif_cond,
                body=elif_block,
                type=UnknownType(),
                is_constexpr=False,
            )
        )

    return elifs


def parse_else_expr(
    state: ParserState, expected_whitespace: WhiteSpaceToken
) -> BlockExpression | None:
    with state.peek() as peeker:
        else_token = state.next_non_whitespace_or_eof()

        if not isinstance(else_token, ElseToken):
            return None

        peeker.drop_peeked_tokens()

    colon = state.next_non_whitespace_or_eof()

    if isinstance(colon, IfToken):
        raise AstError("Unexpected `else if`. Did you mean `elif`?", colon or state.current_token)

    if not isinstance(colon, ColonToken):
        raise AstError("Expected `:`", colon or state.current_token)

    newline = next(state, None)

    if not isinstance(newline, NewlineToken):
        raise AstError("Expected newline", newline or colon)

    whitespace = next(state, None)

    if not isinstance(whitespace, WhiteSpaceToken):
        raise AstError("Expected whitespace", whitespace or newline)

    exprs = cast(list[Expression], generate_block(state, expected_whitespace))

    if not exprs:
        raise AstError("Expected expression", state.current_token)

    return BlockExpression.from_exprs(exprs, expected_whitespace)


def generate_ast_tree(tokens: Iterable[Token]) -> FileNode:
    state = ParserState(list(tokens))

    return FileNode(generate_block(state))


def generate_block(state: ParserState, whitespace: WhiteSpaceToken | None = None) -> list[Node]:
    exprs: list[Node] = []
    expected_whitespace = False

    with state.indent(whitespace):
        for token in state:
            if isinstance(token, CommentToken | NewlineToken):
                continue

            if isinstance(token, WhiteSpaceToken):
                expected_whitespace = False

                if whitespace:
                    if state.is_over_indented(token):
                        raise AstError("Unexpected indentation", token)

                    if state.is_under_indented(token):
                        state.rewind(-2)
                        return exprs

                continue

            if expected_whitespace and whitespace:
                state.rewind(-1)
                return exprs

            exprs.append(generate_node(state))
            expected_whitespace = True

    return exprs


def raise_identifier_suggestion(expr: IdentifierExpression, token: Token) -> NoReturn:
    name = expr.name

    if re.search("run.*on", name, re.IGNORECASE):
        suggestion = f"run_on {token.content} ..."
    else:
        suggestion = f"shell {expr.name} {token.content} ..."

    msg = f"Unexpected identifier `{token.content}`. Did you mean `{suggestion}`?"

    raise AstError(msg, token)


def generate_node(state: ParserState) -> Node:
    token = state.current_token

    if isinstance(token, OnToken):
        return generate_on_stmt(state)

    if isinstance(token, RunOnToken):
        return generate_run_on_stmt(state)

    if isinstance(token, CacheToken):
        return generate_cache_stmt(state)

    if isinstance(token, TitleToken):
        return generate_title_stmt(state)

    if isinstance(token, AtToken | FunctionToken):
        return generate_function_def(state)

    if isinstance(token, ForToken):
        return generate_for_stmt(state)

    if isinstance(token, BreakToken):
        return generate_break_stmt(state)

    if isinstance(token, ContinueToken):
        return generate_continue_stmt(state)

    if isinstance(token, ImportToken):
        return generate_import_stmt(state)

    if isinstance(token, IdentifierToken) and token.content in {
        *SHELL_ALIASES,
        "shell",
    }:
        return generate_shell_function_expr(state)

    expr = generate_expr(state)

    if not isinstance(state.current_token, NewlineToken):
        token = state.next_non_whitespace_or_eof()  # type: ignore

        if token and not isinstance(token, NewlineToken):
            if isinstance(expr, IdentifierExpression):
                raise_identifier_suggestion(expr, token)

            raise AstError("Expected newline", token)

    return expr


def generate_member_expr(token: IdentifierToken) -> MemberExpression:
    members = token.content.split(".")

    if not all(members):
        line_info = LineInfo.from_token(token)
        line_info.column_start += token.content.index(".")

        raise AstError("Unexpected `.` in token", line_info)

    # TODO: don't assume expr ends on same line as it starts
    locations = [
        [token.column_start + column for column, _ in group[1]]
        for group in groupby(
            enumerate(token.content),
            key=lambda data: data[1] != ".",
        )
        if group[0]
    ]

    stack: list[Expression] = []

    for i, location in enumerate(locations):
        name = members[i]

        stack.append(
            IdentifierExpression(
                info=LineInfo(token.line, location[0], token.line, location[-1]),
                type=UnknownType(),
                name=name,
                is_constexpr=False,
            )
        )

        if len(stack) == 2:
            rhs = stack.pop()
            lhs = stack.pop()

            stack.append(
                MemberExpression(
                    info=LineInfo(
                        line=token.line,
                        column_start=lhs.info.column_start,
                        line_end=token.line,
                        column_end=rhs.info.column_end,
                    ),
                    type=UnknownType(),
                    lhs=lhs,
                    name=name,
                    is_constexpr=False,
                )
            )

    assert len(stack) == 1
    assert isinstance(stack[0], MemberExpression)

    return stack[0]


def generate_interpolated_string(state: ParserState, leading_tokens: list[Token]) -> Expression:
    parts: list[Expression] = []

    if leading_tokens:
        parts.append(StringExpression.from_token(Token.meld(leading_tokens)))

    parts.append(
        ShellEscapeExpression.from_expr(ToStringExpression.from_expr(generate_paren_expr(state)))
    )

    if isinstance(state.current_token, DanglingToken | IdentifierToken):
        parts.append(StringExpression.from_token(state.current_token))

        next(state)

    stack = parts.pop()

    for expr in reversed(parts):
        stack = BinaryExpression.from_exprs(
            expr,
            BinaryOperator.ADD,
            stack,
            expr.info,
        )

    return stack


def generate_shell_function_expr(state: ParserState) -> FunctionExpression:
    name = state.current_token

    next_token = next(state, None)

    if next_token and not isinstance(next_token, NewlineToken):
        args = generate_string_list(state)

    else:
        args = []

    if name.content in SHELL_ALIASES:
        shell = replace(name, content="shell")
        callee: Expression = IdentifierExpression.from_token(shell)

        args.insert(0, StringExpression.from_token(name))

    else:
        callee = IdentifierExpression.from_token(name)

    return FunctionExpression(
        info=LineInfo.from_token(name),
        callee=callee,
        args=args,
        type=UnknownType(),
        is_constexpr=False,
        is_shell_mode=True,
    )


def promote_expr_to_func_expr(
    state: ParserState,
    start: Token,
    expr: Expression,
) -> Expression | None:
    with state.peek() as peek:
        oper = state.next_non_whitespace_or_eof()

        if isinstance(oper, OpenParenToken):
            func = generate_c_function_expr(state, start, expr)

            peek.drop_peeked_tokens()

            return func

    return None


def generate_c_function_expr(
    state: ParserState,
    start: Token,
    callee: Expression,
) -> FunctionExpression:
    # TODO: allow non-identifier-like exprs to be callees
    assert isinstance(callee, IdentifierExpression | MemberExpression)

    state.next_non_whitespace()

    args: list[Expression] = []

    if not isinstance(state.current_token, CloseParenToken):
        while True:
            args.append(generate_expr(state))
            state.next_non_whitespace()

            if isinstance(state.current_token, CloseParenToken):
                break

            if not isinstance(state.current_token, CommaToken):
                raise AstError.unexpected_token(state.current_token, expected=",")

            state.next_non_whitespace()

    return FunctionExpression(
        info=LineInfo.from_token(start),
        callee=callee,
        args=args,
        type=UnknownType(),
        is_constexpr=False,
        is_shell_mode=False,
    )


def generate_string_list(
    state: ParserState, *, stop_at: type[Token] | _UnionType = NewlineToken
) -> list[Expression]:
    arg: list[Token] = []
    args: list[Expression] = []

    for token in state:
        if isinstance(token, stop_at):
            break

        if arg and isinstance(token, WhiteSpaceToken):
            args.append(StringExpression.from_token(Token.meld(arg)))

            token = state.next_non_whitespace()
            arg = []

        if isinstance(token, stop_at):
            break

        if isinstance(token, WhiteSpaceToken):
            continue

        if isinstance(token, OpenParenToken):
            leading_tokens = arg

            if arg:
                arg = []

            args.append(generate_interpolated_string(state, leading_tokens))

            if isinstance(state.current_token, stop_at):
                state.rewind(-1)
                break

        else:
            arg.append(token)

    if arg:
        args.append(StringExpression.from_token(Token.meld(arg)))

    return args


def generate_let_expr(state: ParserState) -> LetExpression:
    start = state.current_token
    is_mutable = False

    try:
        name_or_mut = state.next_non_whitespace()

        if isinstance(name_or_mut, MutToken):
            is_mutable = True
            name = state.next_non_whitespace()

        else:
            name = name_or_mut

        if isinstance(name, KeywordToken):
            raise AstError(
                f"Cannot use keyword `{name.content}` as an identifier name",
                name,
            )

        if not isinstance(name, IdentifierToken):
            raise AstError("Expected identifier", name)

        equal = state.next_non_whitespace()

        if not isinstance(equal, EqualToken):
            raise AstError.unexpected_token(equal, expected="=")

        state.next_non_whitespace()

        if isinstance(state.current_token, NewlineToken):
            whitespace = next(state)

            # TODO: move to generate_block
            assert isinstance(whitespace, WhiteSpaceToken)

            exprs = cast(list[Expression], generate_block(state, whitespace))

            expr: Expression = BlockExpression.from_exprs(exprs, whitespace)

        else:
            expr = generate_expr(state)

    except StopIteration as ex:
        raise AstError.expected_token(last=state.current_token) from ex

    return LetExpression(
        is_mutable=is_mutable,
        name=name.content,
        info=LineInfo.from_token(start),
        expr=expr,
        type=expr.type,
        is_constexpr=False,
    )


def generate_paren_expr(state: ParserState) -> ParenthesisExpression:
    token = state.current_token
    state.next_non_whitespace()

    expr = generate_expr(state)

    state.next_non_whitespace()

    if not isinstance(state.current_token, CloseParenToken):
        raise AstError.unexpected_token(state.current_token, expected=")")

    next(state, None)

    return ParenthesisExpression.from_expr(expr, token)


def generate_list_expr(state: ParserState) -> ListExpression:
    start = state.current_token

    if not state.next_non_whitespace_or_eof():
        raise AstError.expected_token(last=start)

    items: list[Expression] = []

    for i in count():
        if isinstance(state.current_token, CommaToken):
            if i == 0:
                # TODO: non-fatal, should be a warning instead
                raise AstError("Leading commas are not allowed", state.current_token)

            token: Token = state.current_token

            if not state.next_non_whitespace_or_eof():
                raise AstError("Expected expression after `,`", token)

        if isinstance(state.current_token, CloseBracketToken):
            break

        items.append(generate_expr(state))

        token = state.current_token

        # TODO: should be "expected , or ]"
        if not state.next_non_whitespace_or_eof():
            raise AstError.expected_token(last=token)

    return ListExpression.from_items(items, start, state.current_token)


def regroup_binary_expr(expr: BinaryExpression) -> None:
    match expr:
        case BinaryExpression(
            lhs,
            oper,
            BinaryExpression(lhs=rhs1, oper=oper2, rhs=rhs2),
        ) if oper.precedence() <= oper2.precedence():
            # TODO: cleanup
            new_lhs = BinaryExpression(
                info=lhs.info,
                lhs=lhs,
                oper=oper,
                rhs=rhs1,
                type=lhs.type,
                is_constexpr=False,
            )

            expr.lhs = new_lhs
            expr.oper = oper2
            expr.rhs = rhs2


def generate_binary_expr(
    state: ParserState,
    start: Token,
    expr: Expression,
) -> Expression | None:
    with state.peek() as peek:
        oper_token = state.next_non_whitespace_or_eof()

        if isinstance(oper_token, NotToken):
            _in = state.next_non_whitespace()

            if not isinstance(_in, InToken):
                raise AstError.unexpected_token(_in, expected="in")

            oper = BinaryOperator.NOT_IN

        # TODO: allow for more oper tokens
        elif isinstance(oper_token, tuple(TOKEN_TO_BINARY_OPER.keys())):
            # TODO: bug in mypy
            assert oper_token

            oper = BinaryOperator.from_token(oper_token)

            if oper == BinaryOperator.IS:
                with state.peek() as peek_is_not:
                    _not = state.next_non_whitespace()

                    if isinstance(_not, NotToken):
                        oper = BinaryOperator.IS_NOT
                        peek_is_not.drop_peeked_tokens()

        else:
            return None

        lhs = expr
        state.next_non_whitespace()
        rhs = generate_expr(state)

        peek.drop_peeked_tokens()

        bin_expr = BinaryExpression.from_exprs(lhs, oper, rhs, start)

        regroup_binary_expr(bin_expr)

        return bin_expr


def generate_expr(state: ParserState) -> Expression:
    token = state.current_token

    expr: Expression | None = None

    if isinstance(token, NotToken):
        state.next_non_whitespace()

        rhs = generate_expr(state)

        expr = UnaryExpression.from_expr(UnaryOperator.NOT, rhs, token)

    elif isinstance(token, MinusToken):
        state.next_non_whitespace()

        rhs = generate_expr(state)

        expr = UnaryExpression.from_expr(UnaryOperator.NEGATE, rhs, token)

    elif isinstance(token, LetToken):
        expr = generate_let_expr(state)

    elif isinstance(token, IfToken):
        expr = generate_if_expr(state)

    elif isinstance(token, ElifToken):
        raise AstError("Unexpected token `elif`. Did you mean `if`?", token)

    elif isinstance(token, ElseToken):
        raise AstError("Unexpected token `else`. Did you mean `if`?", token)

    elif isinstance(token, IntegerLiteralToken | FloatLiteralToken):
        expr = NumericExpression.from_token(token)

    elif isinstance(token, StringLiteralToken):
        expr = StringExpression.from_token(token)

    elif isinstance(token, BooleanLiteralToken):
        expr = BooleanExpression.from_token(token)

    elif isinstance(token, IdentifierToken) and not isinstance(token, KeywordToken):
        if "." in token.content:
            expr = generate_member_expr(token)
        else:
            expr = IdentifierExpression.from_token(token)

    elif isinstance(token, OpenParenToken):
        expr = generate_paren_expr(state)

    elif isinstance(token, OpenBracketToken):
        expr = generate_list_expr(state)

    elif isinstance(token, DanglingToken):
        raise AstError.unexpected_token(token)

    else:
        raise AstError(f"Expected an expression, got `{token.content}`", token)

    if func_expr := promote_expr_to_func_expr(state, token, expr):
        expr = func_expr

    if binary_expr := generate_binary_expr(state, token, expr):
        return binary_expr

    return expr


def generate_on_stmt(state: ParserState) -> OnStatement:
    start = state.current_token

    try:
        event = state.next_non_whitespace()
    except StopIteration as ex:
        raise AstError.expected_token(last=state.current_token) from ex

    where = None

    with state.peek() as peek:
        where_token = state.next_non_whitespace_or_eof()

        if isinstance(where_token, WhereToken):
            state.next_non_whitespace()
            where = generate_expr(state)

            peek.drop_peeked_tokens()

    state.next_newline_or_eof()

    return OnStatement(
        info=LineInfo.from_token(start),
        event=event.content,
        where=where,
    )


def generate_run_on_stmt(state: ParserState) -> RunOnStatement:
    start = state.current_token

    try:
        run_type_token = state.next_non_whitespace()

    except StopIteration as ex:
        raise AstError.expected_token(last=state.current_token) from ex

    try:
        run_type = RunType(run_type_token.content)

    except ValueError as ex:
        content = run_type_token.content

        if re.search("self(.*host|)", content, re.IGNORECASE):
            suggestion = "self_hosted"
        else:
            suggestion = "image"

        msg = f"Invalid `run_on` type `{content}`. Did you mean `{suggestion}`?"

        raise AstError(msg, run_type_token) from ex

    space = next(state, None)

    value = ""

    if run_type == RunType.IMAGE:
        if not isinstance(space, WhiteSpaceToken):
            raise AstError("Expected whitespace", space or run_type_token)

        for token in state:
            if not isinstance(
                token,
                IdentifierToken
                | ColonToken
                | FloatLiteralToken
                | IntegerLiteralToken
                | SlashToken
                | MinusToken
                | CommaToken,
            ):
                break

            value += token.content

        if not value:
            raise AstError.expected_token(last=space)

    # TODO: check newline or EOF is here

    return RunOnStatement(
        info=LineInfo.from_token(start),
        type=run_type,
        value=value,
    )


def generate_cache_stmt(state: ParserState) -> CacheStatement:
    start = state.current_token

    msg = "Invalid `cache` statement. Did you mean `cache file using ...`?"

    try:
        # skip "cache" token
        next(state)

        files = generate_string_list(state, stop_at=UsingToken)

        if not files:
            raise AstError(msg, start)

        using = state.current_token

        if not isinstance(using, UsingToken):
            raise AstError.unexpected_token(using, expected="using")

        state.next_non_whitespace()

        cache_key = generate_expr(state)

        return CacheStatement(
            info=LineInfo.from_token(start),
            files=files,
            using=cache_key,
        )

    except StopIteration as ex:
        raise AstError(msg, start) from ex


def generate_title_stmt(state: ParserState) -> TitleStatement:
    start = state.current_token

    error_msg = "Expected expression after `title`"

    try:
        # skip "title" token
        next(state)

        parts = generate_string_list(state)

        if not parts:
            raise AstError(error_msg, start)

        return TitleStatement(info=LineInfo.from_token(start), parts=parts)

    except StopIteration as ex:
        raise AstError(error_msg, start) from ex


def generate_function_annotations(
    state: ParserState,
) -> list[FunctionAnnotation]:
    at = state.current_token

    if not isinstance(at, AtToken):
        return []

    # skip @ token
    token = next(state, None)

    if not token:
        raise AstError.expected_token(last=at)

    expr = generate_expr(state)

    if not isinstance(expr, IdentifierExpression):
        raise AstError("Expected identifier", expr)

    last = state.current_token

    # skip over identifier
    token = next(state, None)

    if not token:
        raise AstError("Expected function after annotation", last)

    if not isinstance(token, WhiteSpaceToken | NewlineToken):
        raise AstError("Expected whitespace", last)

    last = state.current_token

    # skip whitespace
    token = next(state, None)
    if not token:
        raise AstError("Expected function after annotation", last)

    if isinstance(token, AtToken):
        raise AstError(
            "Multiple function annotations are not supported yet",
            last,
        )

    return [
        FunctionAnnotation(
            info=replace(expr.info, column_start=at.column_start),
            expr=expr,
        )
    ]


def generate_function_def(state: ParserState) -> FunctionDefStatement:
    annotations = generate_function_annotations(state)

    start = state.current_token

    name = state.next_non_whitespace_or_eof()
    if not name:
        raise AstError.expected_token(last=start)

    if isinstance(name, KeywordToken):
        raise AstError(f"Cannot use keyword `{name.content}` as function name", name)

    if not isinstance(name, IdentifierToken):
        raise AstError(f"Expected identifier, got `{name.content}` instead", name)

    open_paren = state.next_non_whitespace_or_eof()
    if not isinstance(open_paren, OpenParenToken):
        raise AstError.unexpected_token(open_paren or name, expected="(")

    arg_names, arg_types = parse_func_def_args(state)

    close_paren: Token | None = state.current_token

    if not isinstance(close_paren, CloseParenToken):
        close_paren = state.next_non_whitespace_or_eof()

    if not isinstance(close_paren, CloseParenToken):
        raise AstError.unexpected_token(close_paren or open_paren, expected=")")

    rtype = parse_func_return_type(state)

    # Use current token since above function advances token for us
    colon = state.current_token

    if not isinstance(colon, ColonToken):
        raise AstError.unexpected_token(colon or close_paren, expected=":")

    newline = next(state, None)
    if not isinstance(newline, NewlineToken):
        raise AstError.unexpected_token(newline or close_paren, expected="\\n")

    whitespace = next(state, None)
    if not isinstance(whitespace, WhiteSpaceToken):
        raise AstError(
            "Expected whitespace after function definition",
            whitespace or newline,
        )

    with state.loop_body(new_scope=True):
        exprs = cast(list[Expression], generate_block(state, whitespace))
        block = BlockExpression.from_exprs(exprs, whitespace)

    return FunctionDefStatement(
        info=LineInfo.from_token(start),
        arg_names=tuple(arg_names),
        name=name.content,
        type=FunctionType(arg_types, rtype=rtype or UnitType()),
        body=block,
        is_constexpr=False,
        annotations=annotations,
    )


def parse_func_def_args(state: ParserState) -> tuple[list[str], list[Type]]:
    # TODO: create an argument dataclass
    arg_names: list[str] = []
    arg_types: list[Type] = []

    with state.peek() as peek:
        arg = state.next_non_whitespace_or_eof()

        if isinstance(arg, IdentifierToken):
            peek.drop_peeked_tokens()

            arg_names.append(arg.content)
            arg_types.append(StringType())

            while True:
                token = state.next_non_whitespace_or_eof()

                # Handle arg type from last argument
                if isinstance(token, ColonToken):
                    arg_types[-1] = generate_type(state)
                    token = state.next_non_whitespace_or_eof()

                if isinstance(token, CloseParenToken):
                    break

                if not isinstance(token, CommaToken):
                    raise AstError(
                        "Expected `,` or `)`",
                        token or arg,
                    )

                arg = state.next_non_whitespace_or_eof()

                if not isinstance(arg, IdentifierToken):
                    raise AstError(
                        "Expected argument",
                        arg or token,
                    )

                arg_names.append(arg.content)
                arg_types.append(StringType())

    assert len(arg_names) == len(arg_types)

    return arg_names, arg_types


def parse_func_return_type(state: ParserState) -> Type | None:
    colon_or_rtype = state.next_non_whitespace_or_eof()

    if not isinstance(colon_or_rtype, MinusToken):
        return None

    arrow = next(state, None)

    if not isinstance(arrow, GreaterThanToken):
        raise AstError.unexpected_token(
            arrow or colon_or_rtype,
            expected="->",
        )

    ty = generate_type(state)

    state.next_non_whitespace_or_eof()

    return ty


def generate_for_stmt(state: ParserState) -> ForStatement:
    start = state.current_token

    name_token = state.next_non_whitespace_or_eof()
    if not isinstance(name_token, IdentifierToken):
        raise AstError("Expected identifier", name_token or start)

    name = IdentifierExpression.from_token(name_token)

    in_token = state.next_non_whitespace_or_eof()
    if not isinstance(in_token, InToken):
        raise AstError.unexpected_token(in_token or name_token, expected="in")

    last = state.current_token
    if not state.next_non_whitespace_or_eof():
        raise AstError("Expected expression after `in`", last)

    source = generate_expr(state)

    last = state.current_token

    colon = state.next_non_whitespace_or_eof()
    if not isinstance(colon, ColonToken):
        raise AstError.unexpected_token(colon or last, expected=":")

    newline = next(state, None)
    if not isinstance(newline, NewlineToken):
        raise AstError.unexpected_token(newline or colon, expected="\\n")

    # TODO: move indented block logic to separate function
    whitespace = next(state, None)
    if not isinstance(whitespace, WhiteSpaceToken):
        raise AstError("Expected indentation in for statement", whitespace or colon)

    with state.loop_body():
        exprs = cast(list[Expression], generate_block(state, whitespace))
        block = BlockExpression.from_exprs(exprs, whitespace)

    return ForStatement(
        info=LineInfo.from_token(start),
        name=name,
        source=source,
        body=block,
        is_constexpr=False,
    )


def generate_type(state: ParserState) -> Type:
    current = state.current_token
    rtype_token = state.next_non_whitespace_or_eof()

    rtype: Type | None = None

    if isinstance(rtype_token, OpenParenToken):
        close_paren = state.next_non_whitespace_or_eof()
        if not isinstance(close_paren, CloseParenToken):
            raise AstError.unexpected_token(
                close_paren or rtype_token,
                expected=")",
            )

        rtype = UnitType()

    elif isinstance(rtype_token, IdentifierToken):
        rtype = string_to_type(rtype_token.content)

    else:
        raise AstError("Expected type", rtype_token or current)

    if not rtype:
        raise AstError(
            f"Unknown type `{rtype_token.content}`",
            rtype_token,
        )

    return rtype


def generate_break_stmt(state: ParserState) -> BreakStatement:
    br = state.current_token

    if not state.is_in_loop():
        raise AstError("Cannot use `break` outside of loop", br)

    return BreakStatement(info=LineInfo.from_token(br))


def generate_continue_stmt(state: ParserState) -> ContinueStatement:
    cont = state.current_token

    if not state.is_in_loop():
        raise AstError("Cannot use `continue` outside of loop", cont)

    return ContinueStatement(info=LineInfo.from_token(cont))


def generate_import_stmt(state: ParserState) -> ImportStatement:
    start = state.current_token

    whitespace = next(state, None)
    if not isinstance(whitespace, WhiteSpaceToken):
        raise AstError("Expected whitespace", start)

    exprs = generate_string_list(state, stop_at=WhiteSpaceToken | NewlineToken)
    if not exprs:
        raise AstError("Expected module name after `import`", whitespace)

    assert len(exprs) == 1

    if not isinstance(exprs[0], StringExpression):
        raise AstError("Interpolated strings are not allowed here", exprs[0])

    newline = state.current_token
    if newline and not isinstance(newline, NewlineToken):
        raise AstError("Expected newline", newline)

    return ImportStatement(info=LineInfo.from_token(start), module=Path(exprs[0].value))
