import re
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from enum import Enum
from itertools import groupby
from typing import NoReturn, Self, cast

from cicada.ast.types import UnknownType
from cicada.parse.token import (
    BooleanLiteralToken,
    CloseParenToken,
    ColonToken,
    CommaToken,
    CommentToken,
    DanglingToken,
    EqualToken,
    FloatLiteralToken,
    IdentifierToken,
    IfToken,
    IntegerLiteralToken,
    KeywordToken,
    LetToken,
    MinusToken,
    MutToken,
    NewlineToken,
    NotToken,
    OnToken,
    OpenParenToken,
    RunOnToken,
    SlashToken,
    StringLiteralToken,
    Token,
    WhereToken,
    WhiteSpaceToken,
)

from .nodes import (
    TOKEN_TO_BINARY_OPER,
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanExpression,
    Expression,
    FileNode,
    FunctionExpression,
    IdentifierExpression,
    IfExpression,
    LetExpression,
    LineInfo,
    MemberExpression,
    Node,
    NumericExpression,
    OnStatement,
    ParenthesisExpression,
    RunOnStatement,
    RunType,
    StringExpression,
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

    def __init__(self, msg: str, info: Token | LineInfo) -> None:
        self.msg = msg
        self.line = info.line
        self.column = info.column_start
        self.filename = None

        super().__init__(str(self))

    @classmethod
    def expected_token(cls, *, last: Token) -> Self:
        return cls(f"expected token after `{last.content}`", last)

    @classmethod
    def unexpected_token(cls, token: Token, *, expected: str = "") -> Self:
        if expected:
            return cls(f"expected `{expected}`", token)

        return cls(f"unexpected token `{token.content}`", token)

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

    def __init__(self, tokens: Sequence[Token]) -> None:
        self.tokens = list(tokens)
        self._current_index = 0
        self._current_indent_level = 0
        self._indent_style = IndentStyle.UNKNOWN

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Token:
        if self._current_index >= len(self.tokens):
            raise StopIteration()

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

    # TODO: turn into func
    return IfExpression(
        info=LineInfo.from_token(start),
        condition=cond,
        body=block,
        type=UnknownType(),
        is_constexpr=False,
    )


def generate_ast_tree(tokens: Iterable[Token]) -> FileNode:
    state = ParserState(list(tokens))

    return FileNode(generate_block(state))


def generate_block(
    state: ParserState, whitespace: WhiteSpaceToken | None = None
) -> list[Node]:
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


def raise_identifier_suggestion(
    expr: IdentifierExpression, token: Token
) -> NoReturn:
    name = expr.name

    if re.search("run.*on", name, re.IGNORECASE):
        suggestion = f"run_on {token.content} ..."
    else:
        suggestion = f"shell {expr.name} {token.content} ..."

    msg = f"Unexpected identifier `{token.content}`. Did you mean `{suggestion}`?"  # noqa: E501

    raise AstError(msg, token)


def generate_node(state: ParserState) -> Node:
    token = state.current_token

    if isinstance(token, OnToken):
        return generate_on_stmt(state)

    if isinstance(token, RunOnToken):
        return generate_run_on_stmt(state)

    if isinstance(token, IdentifierToken) and token.content in {
        *SHELL_ALIASES,
        "shell",
    }:
        return generate_function_expr(state)

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
                info=LineInfo(
                    token.line, location[0], token.line, location[-1]
                ),
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


def generate_interpolated_string(
    state: ParserState, leading_tokens: list[Token]
) -> Expression:
    parts: list[Expression] = []

    if leading_tokens:
        parts.append(StringExpression.from_token(Token.meld(leading_tokens)))

    parts.append(ToStringExpression.from_expr(generate_paren_expr(state)))

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


def generate_function_expr(state: ParserState) -> FunctionExpression:
    name = state.current_token

    arg: list[Token] = []
    args: list[Expression] = []

    next_token = next(state, None)

    if next_token and not isinstance(next_token, NewlineToken):
        for token in state:
            if isinstance(token, NewlineToken):
                break

            if arg and isinstance(token, WhiteSpaceToken):
                args.append(StringExpression.from_token(Token.meld(arg)))

                token = state.next_non_whitespace()
                arg = []

            if isinstance(token, WhiteSpaceToken):
                continue

            if isinstance(token, OpenParenToken):
                leading_tokens = arg

                if arg:
                    arg = []

                args.append(
                    generate_interpolated_string(state, leading_tokens)
                )

                if isinstance(state.current_token, NewlineToken):
                    state.rewind(-1)
                    break

            else:
                arg.append(token)

        if arg:
            args.append(StringExpression.from_token(Token.meld(arg)))

    if name.content in SHELL_ALIASES:
        function_name = "shell"
        args.insert(0, StringExpression.from_token(name))

    else:
        function_name = name.content

    return FunctionExpression(
        info=LineInfo.from_token(name),
        name=function_name,
        args=args,
        type=UnknownType(),
        is_constexpr=False,
    )


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
                f"cannot use keyword `{name.content}` as an identifier name",
                name,
            )

        if not isinstance(name, IdentifierToken):
            raise AstError("expected identifier", name)

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


def generate_expr(state: ParserState) -> Expression:  # noqa: PLR0915
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

    elif isinstance(token, IntegerLiteralToken | FloatLiteralToken):
        expr = NumericExpression.from_token(token)

    elif isinstance(token, StringLiteralToken):
        expr = StringExpression.from_token(token)

    elif isinstance(token, BooleanLiteralToken):
        expr = BooleanExpression.from_token(token)

    elif isinstance(token, IdentifierToken) and not isinstance(
        token, KeywordToken
    ):
        if "." in token.content:
            expr = generate_member_expr(token)
        else:
            expr = IdentifierExpression.from_token(token)

    elif isinstance(token, OpenParenToken):
        expr = generate_paren_expr(state)

    elif isinstance(token, DanglingToken):
        raise AstError.unexpected_token(token)

    else:
        raise AstError(f"expected an expression, got `{token.content}`", token)

    with state.peek() as peek:
        oper = state.next_non_whitespace_or_eof()

        if isinstance(oper, OpenParenToken):
            # TODO: allow non-identifier to be function expressions
            assert isinstance(expr, IdentifierExpression)

            state.next_non_whitespace()

            args: list[Expression] = []

            if not isinstance(state.current_token, CloseParenToken):
                while True:
                    args.append(generate_expr(state))
                    state.next_non_whitespace()

                    if isinstance(state.current_token, CloseParenToken):
                        break

                    if not isinstance(state.current_token, CommaToken):
                        raise AstError.unexpected_token(
                            state.current_token, expected=","
                        )

                    state.next_non_whitespace()

            peek.drop_peeked_tokens()

            return FunctionExpression(
                info=LineInfo.from_token(token),
                name=expr.name,
                args=args,
                type=UnknownType(),
                is_constexpr=False,
                is_shell_mode=False,
            )

        # TODO: allow for more oper tokens
        if isinstance(oper, tuple(TOKEN_TO_BINARY_OPER.keys())):
            # TODO: bug in mypy
            assert oper

            lhs = expr
            state.next_non_whitespace()
            rhs = generate_expr(state)

            peek.drop_peeked_tokens()

            bin_expr = BinaryExpression.from_exprs(
                lhs, BinaryOperator.from_token(oper), rhs, token
            )

            regroup_binary_expr(bin_expr)

            return bin_expr

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

        msg = f"invalid `run_on` type `{content}`. Did you mean `{suggestion}`?"  # noqa: E501

        raise AstError(msg, info=run_type_token) from ex

    space = next(state, None)

    value = ""

    if run_type == RunType.IMAGE:
        if not isinstance(space, WhiteSpaceToken):
            raise AstError("expected whitespace", space or run_type_token)

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
