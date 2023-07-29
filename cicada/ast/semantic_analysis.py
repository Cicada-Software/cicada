from collections import ChainMap
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

from cicada.ast.generate import SHELL_ALIASES, AstError
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    Expression,
    FileNode,
    FunctionExpression,
    IdentifierExpression,
    IfExpression,
    LetExpression,
    MemberExpression,
    OnStatement,
    ParenthesisExpression,
    RunOnStatement,
    ToStringExpression,
    TraversalVisitor,
    UnaryExpression,
    UnaryOperator,
)
from cicada.ast.types import (
    BOOL_LIKE_TYPES,
    BooleanType,
    NumericType,
    RecordField,
    RecordType,
    StringType,
    Type,
    UnionType,
    UnknownType,
)
from cicada.common.json import asjson
from cicada.domain.triggers import Trigger


def json_to_record_type(j: object) -> Type:
    if isinstance(j, dict):
        types = RecordType()

        for k, v in j.items():
            types.fields.append(RecordField(k, json_to_record_type(v)))

        return types

    if isinstance(j, str):
        return StringType()

    if isinstance(j, int):
        return NumericType()

    raise NotImplementedError()


class IgnoreWorkflow(RuntimeError):
    """
    Raised when a workflow should be ignored, usually because the trigger type
    is not applicable to the workflow being ran.
    """


# TODO: wrap around function to provide default
OPERATOR_ALLOWED_TYPES: dict[BinaryOperator, list[type[Type]]] = {
    BinaryOperator.EXPONENT: [NumericType],
    BinaryOperator.MULTIPLY: [NumericType],
    BinaryOperator.DIVIDE: [NumericType],
    BinaryOperator.MODULUS: [NumericType],
    BinaryOperator.ADD: [NumericType, StringType],
    BinaryOperator.SUBTRACT: [NumericType],
    BinaryOperator.AND: [NumericType, BooleanType],
    BinaryOperator.OR: [NumericType, BooleanType],
    BinaryOperator.XOR: [NumericType, BooleanType],
    BinaryOperator.LESS_THAN: [NumericType],
    BinaryOperator.GREATER_THAN: [NumericType],
    BinaryOperator.LESS_THAN_OR_EQUAL: [NumericType],
    BinaryOperator.GREATER_THAN_OR_EQUAL: [NumericType],
    BinaryOperator.IS: [Type],
    BinaryOperator.ASSIGN: [Type],
}


# These is a mapping of binary operators which always coerce their operands to
# a specific type. For instance, an `is` comparison always results in a boolean
# result, whereas an `and` operator can result in either a bool or a number.
OPERATOR_RESULT_TYPES: dict[BinaryOperator, type[Type]] = {
    BinaryOperator.LESS_THAN: BooleanType,
    BinaryOperator.GREATER_THAN: BooleanType,
    BinaryOperator.LESS_THAN_OR_EQUAL: BooleanType,
    BinaryOperator.GREATER_THAN_OR_EQUAL: BooleanType,
    BinaryOperator.IS: BooleanType,
}


STRING_COERCIBLE_TYPES: tuple[Type, ...] = (
    StringType(),
    BooleanType(),
    NumericType(),
)


RESERVED_NAMES = {"event", "env"}


class SemanticAnalysisVisitor(TraversalVisitor):
    function_names: set[str]
    types: dict[str, Type]
    symbols: ChainMap[str, LetExpression]
    trigger: Trigger | None

    # This is set when a function has been called, used to detect non-constexpr
    # functions being called before an `on` statement. There is probably a more
    # elegant way of detecting this, for example, adding a constexpr flag to
    # each statement node.
    has_ran_function: bool

    # Set whenever an `on` statement is found, used to detect if there are
    # multiple on statements defined.
    has_on_stmt: bool

    run_on: RunOnStatement | None

    env: RecordType | None

    file_node: FileNode | None = None

    def __init__(self, trigger: Trigger | None = None) -> None:
        # TODO: populate symbol table with builtins
        self.function_names = {*SHELL_ALIASES, "shell", "print"}
        self.types = {}
        self.symbols = ChainMap()
        self.trigger = trigger
        self.has_ran_function = False
        self.has_on_stmt = False
        self.run_on = None
        self.env = None
        self.file_node = None

        if self.trigger:
            event = cast(RecordType, json_to_record_type(asjson(self.trigger)))
            self.types["event"] = event

            self.env = cast(
                RecordType,
                next(x for x in event.fields if x.name == "env").type,
            )

    def visit_file_node(self, node: FileNode) -> None:
        self.file_node = node

        super().visit_file_node(node)

    def visit_let_expr(self, node: LetExpression) -> None:
        super().visit_let_expr(node)

        if node.name in RESERVED_NAMES:
            raise AstError(f"Name `{node.name}` is reserved", node.info)

        self.symbols[node.name] = node

        if self.is_constexpr(node.expr):
            node.is_constexpr = True

        node.type = node.expr.type

    def visit_member_expr(self, node: MemberExpression) -> None:
        super().visit_member_expr(node)

        if not (
            isinstance(node.lhs.type, RecordType)
            and node.name in {field.name for field in node.lhs.type.fields}
        ):
            # TODO: turn this into a function
            name = cast(IdentifierExpression, node.lhs).name

            raise AstError(
                f"member `{node.name}` does not exist on `{name}`", node.info
            )

        if self.is_constexpr(node.lhs):
            node.is_constexpr = True

        for field in node.lhs.type.fields:
            if field.name == node.name:
                node.type = field.type

    def visit_ident_expr(self, node: IdentifierExpression) -> None:
        super().visit_ident_expr(node)

        if type := self.types.get(node.name):
            node.type = type

        elif node.name == "env" and self.env:
            node.type = self.env

        elif symbol := self.symbols.get(node.name):
            node.type = symbol.expr.type

        else:
            raise AstError(f"variable `{node.name}` is not defined", node.info)

    def visit_paren_expr(self, node: ParenthesisExpression) -> None:
        # TODO: test this

        super().visit_paren_expr(node)

        node.type = node.expr.type

    def visit_unary_expr(self, node: UnaryExpression) -> None:
        super().visit_unary_expr(node)

        if node.oper == UnaryOperator.NOT:
            if node.rhs.type != BooleanType():
                raise AstError(
                    "cannot use `not` operator with non-boolean value",
                    node.info,
                )

        elif node.oper == UnaryOperator.NEGATE:
            if node.rhs.type != NumericType():
                raise AstError(
                    "cannot use `-` operator with non-numeric value", node.info
                )

        else:
            assert False

        if self.is_constexpr(node.rhs):
            node.is_constexpr = True

    def visit_binary_expr(self, node: BinaryExpression) -> None:
        super().visit_binary_expr(node)

        if node.oper == BinaryOperator.ASSIGN:
            if not isinstance(node.lhs, IdentifierExpression):
                raise AstError(
                    "you can only assign to variables", node.lhs.info
                )

            var = self.symbols[node.lhs.name]

            if not var.is_mutable:
                raise AstError(
                    f"cannot assign to immutable variable `{node.lhs.name}` (are you forgetting `mut`?)",  # noqa: E501
                    node.lhs.info,
                )

        if node.lhs.type != node.rhs.type:
            verb = (
                "assigned to"
                if node.oper == BinaryOperator.ASSIGN
                else "used with"
            )

            raise AstError(
                f"expression of type `{node.rhs.type}` cannot be {verb} type `{node.lhs.type}`",  # noqa: E501
                node.rhs.info,
            )

        allowed_types = OPERATOR_ALLOWED_TYPES[node.oper]

        if (
            Type not in allowed_types
            and type(node.lhs.type) not in allowed_types
        ):
            # TODO: move to AstError class
            wrapped = [f"`{ty()}`" for ty in allowed_types]

            if len(wrapped) > 1:
                wrapped[-1] = f"or {wrapped[-1]}"

            types = ", ".join(wrapped)

            raise AstError(
                f"expected type {types}, got type `{node.lhs.type}` instead",
                node.lhs.info,
            )

        if self.is_constexpr(node.lhs) and self.is_constexpr(node.rhs):
            node.is_constexpr = True

        if new_type := OPERATOR_RESULT_TYPES.get(node.oper):
            node.type = new_type()

        else:
            # TODO: test this
            node.type = node.lhs.type

    def visit_func_expr(self, node: FunctionExpression) -> None:
        super().visit_func_expr(node)

        if node.name not in self.function_names:
            raise AstError(f"function `{node.name}` is not defined", node.info)

        self.has_ran_function = True

        node.type = RecordType()

    def visit_on_stmt(self, node: OnStatement) -> None:
        if self.has_on_stmt:
            # TODO: include location of existing on stmt

            raise AstError(
                "cannot use multiple `on` statements in a single file",
                node.info,
            )

        if self.has_ran_function:
            # TODO: include location of offending non-constexpr function

            raise AstError(
                "cannot use `on` statement after a function call", node.info
            )

        super().visit_on_stmt(node)

        if not self.trigger:
            raise AstError(
                "cannot use `on` statement when trigger is not defined",
                node.info,
            )

        if self.trigger.type != node.event:
            raise IgnoreWorkflow(
                f"`{self.trigger.type}` doesn't match `{node.event}`",
                node.info,
            )

        if node.where:
            if not self.is_constexpr(node.where):
                raise AstError(
                    "`where` clause must be a constant expression",
                    node.where.info,
                )

            if node.where.type != BooleanType():
                raise AstError(
                    "`where` clause must be a boolean type", node.where.info
                )

        self.has_on_stmt = True

    def visit_run_on_stmt(self, node: RunOnStatement) -> None:
        super().visit_run_on_stmt(node)

        if self.has_ran_function:
            raise AstError(
                "cannot use `run_on` statement after a function call",
                node.info,
            )

        if self.run_on:
            raise AstError(
                "cannot use multiple `run_on` statements in a single file",
                node.info,
            )

        # TODO: use run_on field from field_node instead
        self.run_on = node

        if self.file_node:
            self.file_node.run_on = node

    def visit_if_expr(self, node: IfExpression) -> None:
        with self.new_scope():
            super().visit_if_expr(node)

            if node.condition.type not in BOOL_LIKE_TYPES:
                raise AstError(
                    f"Type `{node.condition.type}` cannot be converted to bool",  # noqa: E501
                    node.condition.info,
                )

            node.is_constexpr = node.body.is_constexpr
            node.type = UnionType((node.body.type, UnknownType()))

    def visit_block_expr(self, node: BlockExpression) -> None:
        super().visit_block_expr(node)

        if not node.exprs:  # pragma: no cover
            raise AstError("Block cannot be empty", node.info)

        node.is_constexpr = all(self.is_constexpr(x) for x in node.exprs)
        node.type = node.exprs[-1].type

    def visit_to_string_expr(self, node: ToStringExpression) -> None:
        super().visit_to_string_expr(node)

        if node.expr.type not in STRING_COERCIBLE_TYPES:
            raise AstError(
                f"cannot convert type `{node.expr.type}` to `{StringType()}`",
                node.expr.info,
            )

        node.type = StringType()

    @contextmanager
    def new_scope(self) -> Iterator[None]:
        self.symbols = self.symbols.new_child()

        yield

        self.symbols = self.symbols.parents

    def is_constexpr(self, node: Expression) -> bool:
        if isinstance(node, IdentifierExpression):
            if symbol := self.symbols.get(node.name):
                return symbol.expr.is_constexpr

            if self.types.get(node.name):
                return True

            return False

        return node.is_constexpr
