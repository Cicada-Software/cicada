from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from itertools import groupby
from typing import cast

from cicada.ast.types import UnknownType
from cicada.parse.token import (
    BooleanLiteralToken,
    CloseParenToken,
    ColonToken,
    CommentToken,
    DanglingToken,
    EqualToken,
    IdentifierToken,
    IfToken,
    IntegerLiteralToken,
    KeywordToken,
    LetToken,
    MinusToken,
    NewlineToken,
    NotToken,
    OnToken,
    OpenParenToken,
    StringLiteralToken,
    Token,
    WhereToken,
    WhiteSpaceToken,
)

from .nodes import (
    TOKEN_TO_BINARY_OPER,
    BinaryExpression,
    BinaryOperator,
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
    StringExpression,
    UnaryExpression,
    UnaryOperator,
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
    def expected_token(cls, *, last: Token) -> AstError:
        return cls(f"expected token after `{last.content}`", last)

    @classmethod
    def unexpected_token(cls, token: Token, *, expected: str) -> AstError:
        return cls(f"expected `{expected}`", token)

    def __str__(self) -> str:
        parts = [
            self.filename or "<unknown>",
            self.line,
            self.column,
            f" {self.msg}",
        ]

        return ":".join(str(x) for x in parts)


class ParserState:
    tokens: Iterator[Token]
    _current_token: Token | None

    _peeked_tokens: list[list[Token]]
    _peek_depth: int

    def __init__(self, tokens: Iterable[Token]) -> None:
        self.tokens = iter(tokens)
        self._current_token = None

        self._peeked_tokens = []
        self._peek_depth = 0

    def __iter__(self) -> ParserState:
        return self

    def __next__(self) -> Token:
        if self._peek_depth:
            self._current_token = next(self.tokens)
            self._peeked_tokens[-1].append(self._current_token)
        else:
            if self._peeked_tokens:
                while True:
                    if not self._peeked_tokens:
                        self._current_token = next(self.tokens)
                        break

                    if self._peeked_tokens[0]:
                        self._current_token = self._peeked_tokens[0].pop(0)
                        break

                    self._peeked_tokens.pop(0)

            else:
                self._current_token = next(self.tokens)

        return self._current_token

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

        self._peek_depth += 1
        old_current = self._current_token
        index = len(self._peeked_tokens)
        self._peeked_tokens.append([])

        peeker = self.Peeker()
        yield peeker

        if peeker.drop_tokens:
            self._peeked_tokens.pop(index)
        else:
            self._current_token = old_current

        self._peek_depth -= 1

    def push_front(self, token: Token) -> None:
        self._peeked_tokens.append([token])

    @property
    def current_token(self) -> Token:
        assert self._current_token
        return self._current_token


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

    body = generate_block(state, expected_whitespace)

    # TODO: turn into func
    return IfExpression(
        info=LineInfo.from_token(start),
        condition=cond,
        body=cast(list[Expression], body),
        type=UnknownType(),
        is_constexpr=False,
    )


def generate_ast_tree(tokens: Iterable[Token]) -> FileNode:
    state = ParserState(tokens)

    return FileNode(generate_block(state))


def generate_block(
    state: ParserState, whitespace: WhiteSpaceToken | None = None
) -> list[Node]:
    exprs: list[Node] = []
    expected_whitespace = False

    for token in state:
        if isinstance(token, CommentToken):
            continue

        if isinstance(token, NewlineToken):
            expected_whitespace = True
            continue

        if isinstance(token, WhiteSpaceToken):
            expected_whitespace = False

            if whitespace:
                # TODO: replace with better error message
                assert token.content == whitespace.content

            continue

        if expected_whitespace and whitespace:
            state.push_front(token)
            return exprs

        exprs.append(generate_node(state))

    return exprs


def generate_node(state: ParserState) -> Node:
    token = state.current_token

    if isinstance(token, LetToken):
        return generate_let_expr(state)

    if isinstance(token, OnToken):
        return generate_on_stmt(state)

    if isinstance(token, IfToken):
        return generate_if_expr(state)

    if isinstance(token, IdentifierToken):
        if "." in token.content:
            # TODO: use ident/member expr as callee for function expr
            return generate_member_expr(token)

        return generate_function_expr(state)

    raise NotImplementedError()


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

    parts.append(generate_paren_expr(state))

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


SHELL_ALIASES = {
    "cd",
    "cp",
    "echo",
    "git",
    "ls",
    "make",
    "mkdir",
    "rm",
}


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

    try:
        name = state.next_non_whitespace()
        equal = state.next_non_whitespace()

        if not isinstance(equal, EqualToken):
            raise AstError.unexpected_token(equal, expected="=")

        state.next_non_whitespace()
        expr = generate_expr(state)

    except StopIteration as ex:
        raise AstError.expected_token(last=state.current_token) from ex

    state.next_newline_or_eof()

    return LetExpression(
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

    elif isinstance(token, IntegerLiteralToken):
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

    else:
        assert False

    with state.peek() as peek:
        oper = state.next_non_whitespace_or_eof()

        if isinstance(oper, EqualToken):
            raise AstError(
                "Unexpected operator `=`, did you mean `is` instead?",
                oper,
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
