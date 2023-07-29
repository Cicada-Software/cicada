from __future__ import annotations

from abc import ABC, abstractmethod
from ast import literal_eval as python_literal_eval
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, auto
from textwrap import indent
from typing import TYPE_CHECKING, Final, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from typing import Self

from cicada.parse.token import (
    AndToken,
    AsteriskToken,
    EqualToken,
    GreaterThanOrEqualToken,
    GreaterThanToken,
    IsToken,
    LessThanOrEqualToken,
    LessThanToken,
    MinusToken,
    ModToken,
    OrToken,
    PlusToken,
    PowerToken,
    SlashToken,
    Token,
    XorToken,
)

from .types import (
    BooleanType,
    NumericType,
    StringType,
    Type,
    UnitType,
    UnknownType,
    UnreachableType,
)


@dataclass
class LineInfo:
    line: int
    column_start: int
    line_end: int
    column_end: int

    @classmethod
    def from_token(cls, token: Token) -> Self:
        return cls(
            token.line, token.column_start, token.line, token.column_end
        )

    def __str__(self) -> str:
        return f"{self.line}:{self.column_start}..{self.line_end}:{self.column_end}"  # noqa: E501


class Value:
    """
    A Value is used to store values of expressions during runtime, or constant
    values which can be known at compile time (such as literals).
    """

    type: Type


class UnitValue(Value):
    type: Type = field(default_factory=UnitType)


class UnreachableValue(Value):
    type: Type = field(default_factory=UnreachableType)


@dataclass
class NumericValue(Value):
    value: Decimal
    type: Type = field(default_factory=NumericType)


@dataclass
class StringValue(Value):
    value: str
    type: Type = field(default_factory=StringType)


@dataclass
class BooleanValue(Value):
    value: bool
    type: Type = field(default_factory=BooleanType)


@dataclass
class RecordValue(Value):
    value: dict[str, Value]
    type: Type


T = TypeVar("T")


@dataclass
class Node(ABC):
    info: LineInfo

    @abstractmethod
    def accept(self, visitor: NodeVisitor[T]) -> T:
        raise NotImplementedError()


@dataclass
class Expression(Node):
    """
    Abstract class representing an expression. All expressions must derive from
    this class.

    An expression must have a type, and must define whether it is a constant
    expression or not. A constant expression is something that can be
    determined during compile time, or before the runtime is executed (on the
    runner).
    """

    type: Type
    is_constexpr: bool


@dataclass
class BlockExpression(Expression):
    """
    A block expr is an expression which is comprised of a list of expressions,
    the last expression being the result of the block.
    """

    __match_args__ = ("exprs",)

    exprs: list[Expression]
    indentation: int
    is_tabs: bool

    @classmethod
    def from_exprs(
        cls, exprs: Sequence[Expression], whitespace: Token
    ) -> Self:
        # TODO: throw AstError
        assert exprs

        return cls(
            exprs=list(exprs),
            indentation=len(whitespace.content),
            is_tabs=whitespace.content[0] == "\t",
            info=LineInfo(
                line=exprs[0].info.line,
                column_start=exprs[0].info.column_start,
                line_end=exprs[-1].info.line_end,
                column_end=exprs[-1].info.column_start,
            ),
            type=exprs[-1].type,
            is_constexpr=False,
        )

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_block_expr(self)

    def __str__(self) -> str:
        body = "\n".join(f"{i}={expr}" for i, expr in enumerate(self.exprs))
        body = indent(body, "  ")

        return f"{type(self).__name__}: # {self.info}\n{body}"


@dataclass
class FileNode:
    """
    The root of the Cicada AST tree. FileNode represents a single Cicada file,
    and all nodes are traversable from here.

    Given that Cicada is expression-based, at the top level, a Cicada file is
    composed of a list of expressions.
    """

    exprs: list[Node]
    file: Path | None = None
    run_on: RunOnStatement | None = None

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_file_node(self)

    def __str__(self) -> str:
        nodes = "\n".join(str(expr) for expr in self.exprs)
        nodes = indent(nodes, "  ")

        return f"{type(self).__name__}:\n{nodes}"


@dataclass
class FunctionExpression(Expression):
    """
    A function call. This function call can be in the traditional C-style:

    f(x, y, z)

    Or in shell-style:

    f x y z
    """

    name: str
    args: list[Expression]
    is_shell_mode: bool = True

    __match_args__ = ("name", "args", "is_shell_mode")

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_func_expr(self)

    def __str__(self) -> str:
        shell = self.is_shell_mode

        args = "\n".join(f"{i}={arg}" for i, arg in enumerate(self.args))
        args = indent(args, "  ")

        return f"{type(self).__name__}(shell={shell}): # {self.info}\n{args}"


@dataclass
class LetExpression(Expression):
    """
    A single let expression (variable declaration).
    """

    is_mutable: bool
    name: str
    expr: Expression

    __match_args__ = ("name", "expr", "is_mutable")

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_let_expr(self)

    def __str__(self) -> str:
        args = f"name={self.name}\nexpr={self.expr}"
        args = indent(args, "  ")

        mut = "mutable" if self.is_mutable else ""

        return f"{type(self).__name__}({mut}): # {self.info}\n{args}"


@dataclass
class IdentifierExpression(Expression):
    """
    A expression representing a variable, such as `x`.
    """

    name: str

    __match_args__ = ("name",)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_ident_expr(self)

    def __str__(self) -> str:
        return f"{type(self).__name__}({self.name!r}) # {self.info}"

    @classmethod
    def from_token(cls, token: Token) -> Self:
        return cls(
            info=LineInfo.from_token(token),
            type=UnknownType(),
            name=token.content,
            is_constexpr=False,
        )


@dataclass
class MemberExpression(Expression):
    """
    A dot expression, such as `x.y`. These expressions are normally built from
    an IdentifierToken, but this might not always be safe to do, because some
    IdentifierTokens end up as strings.

    For instance, the following dotted identifier (`python3.10`) is used in a
    string context, but would be invalid in a normal expression context:

    shell python3.10 --version
    """

    lhs: Expression
    name: str

    __match_args__ = ("lhs", "name")

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_member_expr(self)

    def __str__(self) -> str:
        args = f"lhs={self.lhs}\nname={self.name}"
        args = indent(args, "  ")

        return f"{type(self).__name__}(): # {self.info}\n{args}"


@dataclass
class StringExpression(Expression, StringValue):
    is_constexpr: bool = True

    __match_args__ = ("value",)

    @classmethod
    def from_token(cls, token: Token) -> Self:
        contents = token.content

        # TODO: test this
        if contents.startswith("'"):
            contents = f"''{contents}''"
        elif contents.startswith('"'):
            contents = f'""{contents}""'
        else:
            contents = f'"""{contents}"""'

        value = python_literal_eval(contents)

        assert isinstance(value, str)

        return cls(
            info=LineInfo.from_token(token),
            value=value,
            type=StringType(),
        )

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_str_expr(self)

    def __str__(self) -> str:
        return f"{type(self).__name__}({self.value!r}) # {self.info}"


@dataclass
class BooleanExpression(Expression, BooleanValue):
    is_constexpr: bool = True

    __match_args__ = ("value",)

    @classmethod
    def from_token(cls, token: Token) -> Self:
        return cls(
            info=LineInfo.from_token(token),
            value=token.content == "true",
            type=BooleanType(),
        )

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_bool_expr(self)

    def __str__(self) -> str:
        return f"{type(self).__name__}({self.value!r}) # {self.info}"


@dataclass
class ParenthesisExpression(Expression):
    expr: Expression

    __match_args__ = ("expr",)

    @classmethod
    def from_expr(cls, expr: Expression, paren: Token) -> Self:
        return cls(
            info=LineInfo.from_token(paren),
            expr=expr,
            type=expr.type,
            is_constexpr=False,
        )

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_paren_expr(self)

    def __str__(self) -> str:
        expr = indent(str(self.expr), "  ")

        return f"{type(self).__name__}: # {self.info}\n{expr}"


@dataclass
class NumericExpression(Expression, NumericValue):
    is_constexpr: bool = True

    __match_args__ = ("value",)

    @classmethod
    def from_token(cls, token: Token) -> Self:
        try:
            value = Decimal(int(token.content, 0))
        except ValueError:
            value = Decimal(token.content)

        return cls(
            info=LineInfo.from_token(token),
            value=value,
            type=NumericType(),
        )

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_num_expr(self)

    def __str__(self) -> str:
        return f"{type(self).__name__}({self.value}) # {self.info}"


class UnaryOperator(Enum):
    NOT = auto()
    NEGATE = auto()


@dataclass
class UnaryExpression(Expression):
    rhs: Expression
    oper: UnaryOperator

    __match_args__ = ("oper", "rhs")

    @classmethod
    def from_expr(
        cls, oper: UnaryOperator, expr: Expression, token: Token
    ) -> Self:
        return cls(
            info=LineInfo.from_token(token),
            rhs=expr,
            oper=oper,
            type=expr.type,
            is_constexpr=False,
        )

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_unary_expr(self)

    def __str__(self) -> str:
        expr = indent(str(self.rhs), "  ")

        return f"{type(self).__name__}({self.oper}): # {self.info}\n{expr}"


class BinaryOperator(Enum):
    """
    Binary operators ordered by precedence. Since operators with the same
    precedence cannot have the same value, floats are used instead. To get the
    real precedence, convert the value to an int by using the precedence()
    function.
    """

    ASSIGN = 0.0
    EXPONENT = 1.0
    MULTIPLY = 2.1
    DIVIDE = 2.2
    MODULUS = 2.3
    ADD = 3.0
    SUBTRACT = 3.1
    AND = 4.0
    OR = 4.1
    XOR = 4.2
    LESS_THAN = 5.0
    GREATER_THAN = 5.1
    LESS_THAN_OR_EQUAL = 5.2
    GREATER_THAN_OR_EQUAL = 5.3
    IS = 6.0
    IS_NOT = 6.1

    @classmethod
    def from_token(cls, token: Token) -> Self:
        if op := TOKEN_TO_BINARY_OPER.get(type(token)):
            return cls(op.value)

        raise NotImplementedError()

    def precedence(self) -> int:
        return int(self.value)


TOKEN_TO_BINARY_OPER: Final[dict[type[Token], BinaryOperator]] = {
    PowerToken: BinaryOperator.EXPONENT,
    AsteriskToken: BinaryOperator.MULTIPLY,
    SlashToken: BinaryOperator.DIVIDE,
    ModToken: BinaryOperator.MODULUS,
    PlusToken: BinaryOperator.ADD,
    MinusToken: BinaryOperator.SUBTRACT,
    AndToken: BinaryOperator.AND,
    OrToken: BinaryOperator.OR,
    XorToken: BinaryOperator.XOR,
    LessThanToken: BinaryOperator.LESS_THAN,
    LessThanOrEqualToken: BinaryOperator.LESS_THAN_OR_EQUAL,
    GreaterThanToken: BinaryOperator.GREATER_THAN,
    GreaterThanOrEqualToken: BinaryOperator.GREATER_THAN_OR_EQUAL,
    IsToken: BinaryOperator.IS,
    # IsNotToken: BinaryOperator.IS_NOT,
    EqualToken: BinaryOperator.ASSIGN,
}


@dataclass
class BinaryExpression(Expression):
    lhs: Expression
    oper: BinaryOperator
    rhs: Expression

    __match_args__ = ("lhs", "oper", "rhs")

    @classmethod
    def from_exprs(
        cls,
        lhs: Expression,
        oper: BinaryOperator,
        rhs: Expression,
        token: Token | LineInfo,
    ) -> Self:
        return cls(
            info=(
                LineInfo.from_token(token)
                if isinstance(token, Token)
                else token
            ),
            lhs=lhs,
            oper=oper,
            rhs=rhs,
            type=lhs.type,
            is_constexpr=False,
        )

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_binary_expr(self)

    def __str__(self) -> str:
        expr = indent("\n".join([str(self.lhs), str(self.rhs)]), "  ")

        return f"{type(self).__name__}({self.oper}): # {self.info}\n{expr}"


@dataclass
class IfExpression(Expression):
    """
    An if expression is like an if statement, except that it can be directly
    assigned to a variable, like any other expression. The result of an if
    expression is the last expression to be evaluated in the if statement.
    """

    __match_args__ = ("condition", "body")

    condition: Expression
    body: BlockExpression

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_if_expr(self)

    def __str__(self) -> str:
        args = f"cond={self.condition}\nbody={self.body}"
        args = indent(args, "  ")

        return f"{type(self).__name__}: # {self.info}\n{args}"


@dataclass
class ToStringExpression(Expression):
    """
    This is a placeholder that is used internally to indicate that a value
    should be converted to a string. Since Cicada currently does not support
    user defined functions, this node is used as a stand in until then.
    """

    __match_args__ = ("expr",)

    expr: Expression

    @classmethod
    def from_expr(cls, expr: Expression) -> Self:
        return cls(
            info=expr.info,
            expr=expr,
            type=expr.type,
            is_constexpr=False,
        )

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_to_string_expr(self)

    def __str__(self) -> str:
        return f"{type(self).__name__}: # {self.info}\n  expr={self.expr}"


@dataclass
class Statement(Node):
    """
    Abstract class representing a statement. Statements cannot be used as
    expressions. They normally dictate things such as control flow.
    """

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_stmt(self)  # pragma: no cover


EventType = str


@dataclass
class OnStatement(Statement):
    event: EventType
    where: Expression | None = None

    __match_args__ = ("event",)

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_on_stmt(self)

    def __str__(self) -> str:
        return f"{type(self).__name__}({self.event!r}) # {self.info}"


class RunType(Enum):
    IMAGE = "image"
    SELF_HOSTED = "self_hosted"


@dataclass
class RunOnStatement(Statement):
    type: RunType
    value: str

    __match_args__ = ("type", "value")

    def accept(self, visitor: NodeVisitor[T]) -> T:
        return visitor.visit_run_on_stmt(self)

    def __str__(self) -> str:
        return "".join(
            [
                type(self).__name__,
                f"({self.type.value}:{self.value})",
                f" # {self.info}",
            ]
        )


class NodeVisitor(Generic[T]):
    def visit_file_node(self, node: FileNode) -> T:
        raise NotImplementedError()

    def visit_func_expr(self, node: FunctionExpression) -> T:
        raise NotImplementedError()

    def visit_let_expr(self, node: LetExpression) -> T:
        raise NotImplementedError()

    def visit_ident_expr(self, node: IdentifierExpression) -> T:
        raise NotImplementedError()

    def visit_member_expr(self, node: MemberExpression) -> T:
        raise NotImplementedError()

    def visit_str_expr(self, node: StringExpression) -> T:
        raise NotImplementedError()

    def visit_bool_expr(self, node: BooleanExpression) -> T:
        raise NotImplementedError()

    def visit_num_expr(self, node: NumericExpression) -> T:
        raise NotImplementedError()

    def visit_paren_expr(self, node: ParenthesisExpression) -> T:
        raise NotImplementedError()

    def visit_stmt(self, node: Statement) -> T:
        raise NotImplementedError()

    def visit_on_stmt(self, node: OnStatement) -> T:
        raise NotImplementedError()

    def visit_if_expr(self, node: IfExpression) -> T:
        raise NotImplementedError()

    def visit_unary_expr(self, node: UnaryExpression) -> T:
        raise NotImplementedError()

    def visit_binary_expr(self, node: BinaryExpression) -> T:
        raise NotImplementedError()

    def visit_block_expr(self, node: BlockExpression) -> T:
        raise NotImplementedError()

    def visit_to_string_expr(self, node: ToStringExpression) -> T:
        raise NotImplementedError()

    def visit_run_on_stmt(self, node: RunOnStatement) -> T:
        raise NotImplementedError()


class TraversalVisitor(NodeVisitor[None]):
    def visit_file_node(self, node: FileNode) -> None:
        for expr in node.exprs:
            expr.accept(self)

    def visit_func_expr(self, node: FunctionExpression) -> None:
        for arg in node.args:
            arg.accept(self)

    def visit_let_expr(self, node: LetExpression) -> None:
        node.expr.accept(self)

    def visit_ident_expr(self, node: IdentifierExpression) -> None:
        pass

    def visit_member_expr(self, node: MemberExpression) -> None:
        node.lhs.accept(self)

    def visit_str_expr(self, node: StringExpression) -> None:
        pass

    def visit_bool_expr(self, node: BooleanExpression) -> None:
        pass

    def visit_num_expr(self, node: NumericExpression) -> None:
        pass

    def visit_paren_expr(self, node: ParenthesisExpression) -> None:
        node.expr.accept(self)

    def visit_stmt(self, node: Statement) -> None:
        pass  # pragma: no cover

    def visit_on_stmt(self, node: OnStatement) -> None:
        if node.where:
            node.where.accept(self)

    def visit_unary_expr(self, node: UnaryExpression) -> None:
        node.rhs.accept(self)

    def visit_binary_expr(self, node: BinaryExpression) -> None:
        node.lhs.accept(self)
        node.rhs.accept(self)

    def visit_if_expr(self, node: IfExpression) -> None:
        node.condition.accept(self)

        node.body.accept(self)

    def visit_block_expr(self, node: BlockExpression) -> None:
        for expr in node.exprs:
            expr.accept(self)

    def visit_to_string_expr(self, node: ToStringExpression) -> None:
        node.expr.accept(self)

    def visit_run_on_stmt(self, node: RunOnStatement) -> None:
        pass
