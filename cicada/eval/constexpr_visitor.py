from collections import ChainMap
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import cast

from cicada.ast.common import trigger_to_record
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanExpression,
    BooleanValue,
    Expression,
    FileNode,
    FunctionDefStatement,
    FunctionExpression,
    FunctionValue,
    IdentifierExpression,
    IfExpression,
    LetExpression,
    MemberExpression,
    NodeVisitor,
    NumericExpression,
    NumericValue,
    OnStatement,
    ParenthesisExpression,
    RecordValue,
    RunOnStatement,
    StringExpression,
    StringValue,
    TitleStatement,
    ToStringExpression,
    UnaryExpression,
    UnaryOperator,
    UnitValue,
    UnreachableValue,
    Value,
)
from cicada.domain.triggers import Trigger


def value_to_string(value: Value) -> Value:
    match value:
        case StringValue():
            return value

        case NumericValue():
            return StringValue(str(value.value))

        case BooleanValue():
            return StringValue("true" if value.value else "false")

    return UnreachableValue()  # pragma: no cover


class WorkflowFailure(ValueError):
    def __init__(self, return_code: int) -> None:
        self.return_code = return_code


class CommandFailed(WorkflowFailure):
    pass


class ConstexprEvalVisitor(NodeVisitor[Value]):
    """
    The constexpr visitor is a visitor which only evaluates expressions which
    are constant expressions. This is primarily for efficiency and safety:
    efficiency in that it allows for pre-evaluating semanticly sound AST trees
    without spinning up a sandboxed environment to run them, and safety in that
    you can evaluate an AST tree using this visitor and be sure that no bad
    things happen (arbitrary shell commands, etc).
    """

    symbols: ChainMap[str, Value]
    trigger: Trigger | None

    def __init__(self, trigger: Trigger | None = None) -> None:
        self.symbols = ChainMap()
        self.trigger = trigger

        if trigger:
            event = cast(RecordValue, trigger_to_record(trigger))

            self.symbols["event"] = event
            self.symbols["env"] = event.value["env"]
            self.symbols["secret"] = event.value["secret"]

    def visit_file_node(self, node: FileNode) -> Value:
        for expr in node.exprs:
            match expr.accept(self):
                case UnreachableValue():
                    return UnreachableValue()

        return UnitValue()

    def visit_member_expr(self, node: MemberExpression) -> Value:
        lhs = node.lhs.accept(self)

        assert isinstance(lhs, RecordValue)

        return lhs.value[node.name]

    def visit_let_expr(self, node: LetExpression) -> Value:
        expr = node.expr.accept(self)

        self.symbols[node.name] = expr

        return expr

    def visit_ident_expr(self, node: IdentifierExpression) -> Value:
        return self.symbols[node.name]

    def visit_paren_expr(self, node: ParenthesisExpression) -> Value:
        return node.expr.accept(self)

    def visit_num_expr(self, node: NumericExpression) -> Value:
        return NumericValue(node.value)

    def visit_str_expr(self, node: StringExpression) -> Value:
        return StringValue(node.value)

    def visit_bool_expr(self, node: BooleanExpression) -> Value:
        return BooleanValue(node.value)

    def visit_unary_expr(self, node: UnaryExpression) -> Value:
        if node.oper == UnaryOperator.NOT:
            rhs = node.rhs.accept(self)

            assert isinstance(rhs, BooleanValue)

            return BooleanValue(not rhs.value)

        if node.oper == UnaryOperator.NEGATE:
            rhs = node.rhs.accept(self)

            assert isinstance(rhs, NumericValue)

            return NumericValue(-rhs.value)

        raise NotImplementedError

    def visit_binary_expr(self, node: BinaryExpression) -> Value:
        # TODO: simplify

        rhs = node.rhs.accept(self)

        if node.oper == BinaryOperator.ASSIGN:
            if isinstance(node.lhs, IdentifierExpression):
                self.reassign_variable(node.lhs.name, rhs)

            if isinstance(node.lhs, MemberExpression):
                # TODO: dont re-eval
                root = node.lhs.lhs.accept(self)
                assert isinstance(root, RecordValue)

                root.value[node.lhs.name] = rhs

            return rhs

        lhs = node.lhs.accept(self)

        if node.oper in (BinaryOperator.IS, BinaryOperator.IS_NOT):
            try:
                return BooleanValue(
                    lhs.value == rhs.value  # type: ignore
                    if node.oper == BinaryOperator.IS
                    else lhs.value != rhs.value  # type: ignore
                )

            except TypeError as ex:  # pragma: no cover
                raise NotImplementedError from ex

        if isinstance(lhs, StringValue) and isinstance(rhs, StringValue):
            if node.oper == BinaryOperator.ADD:
                return StringValue(lhs.value + rhs.value)

            if node.oper == BinaryOperator.IN:
                return BooleanValue(lhs.value in rhs.value)

            if node.oper == BinaryOperator.NOT_IN:
                return BooleanValue(lhs.value not in rhs.value)

        elif isinstance(lhs, NumericValue) and isinstance(rhs, NumericValue):
            if node.oper == BinaryOperator.EXPONENT:
                return NumericValue(lhs.value**rhs.value)

            if node.oper == BinaryOperator.ADD:
                return NumericValue(lhs.value + rhs.value)

            if node.oper == BinaryOperator.SUBTRACT:
                return NumericValue(lhs.value - rhs.value)

            if node.oper == BinaryOperator.MULTIPLY:
                return NumericValue(lhs.value * rhs.value)

            if node.oper == BinaryOperator.DIVIDE:
                # TODO: move this to semantic layer
                return NumericValue(lhs.value / rhs.value)

            if node.oper == BinaryOperator.MODULUS:
                return NumericValue(lhs.value % rhs.value)

            if node.oper == BinaryOperator.AND:
                return NumericValue(Decimal(int(lhs.value) & int(rhs.value)))

            if node.oper == BinaryOperator.OR:
                return NumericValue(Decimal(int(lhs.value) | int(rhs.value)))

            if node.oper == BinaryOperator.XOR:
                return NumericValue(Decimal(int(lhs.value) ^ int(rhs.value)))

            if node.oper == BinaryOperator.LESS_THAN:
                return BooleanValue(lhs.value < rhs.value)

            if node.oper == BinaryOperator.GREATER_THAN:
                return BooleanValue(lhs.value > rhs.value)

            if node.oper == BinaryOperator.LESS_THAN_OR_EQUAL:
                return BooleanValue(lhs.value <= rhs.value)

            if node.oper == BinaryOperator.GREATER_THAN_OR_EQUAL:
                return BooleanValue(lhs.value >= rhs.value)

        elif isinstance(lhs, BooleanValue) and isinstance(rhs, BooleanValue):
            if node.oper == BinaryOperator.AND:
                return BooleanValue(lhs.value and rhs.value)

            if node.oper == BinaryOperator.OR:
                return BooleanValue(lhs.value or rhs.value)

            if node.oper == BinaryOperator.XOR:
                return BooleanValue(lhs.value ^ rhs.value)

        raise NotImplementedError

    def visit_on_stmt(self, node: OnStatement) -> Value:
        assert self.trigger

        if node.event != self.trigger.type:
            return UnreachableValue()

        if node.where:
            should_run = node.where.accept(self)

            if isinstance(should_run, BooleanValue) and should_run.value:
                return should_run

            return UnreachableValue()

        return BooleanValue(True)

    def visit_if_expr(self, node: IfExpression) -> Value:
        with self.new_scope():
            cond = node.condition.accept(self)

            assert isinstance(cond, BooleanValue | NumericValue | StringValue)

            if cond.value:
                return node.body.accept(self)

            return UnitValue()

    def visit_block_expr(self, node: BlockExpression) -> Value:
        last: Value = UnitValue()

        for expr in node.exprs:
            last = expr.accept(self)

        return last

    def visit_to_string_expr(self, node: ToStringExpression) -> Value:
        value = node.expr.accept(self)

        return value_to_string(value)

    def visit_run_on_stmt(self, node: RunOnStatement) -> Value:
        return UnitValue()

    def visit_func_expr(self, node: FunctionExpression) -> Value:
        if not isinstance(node.callee, MemberExpression):
            return NotImplemented

        # TODO: use member function types
        expr = cast(StringValue, node.callee.lhs.accept(self))
        args = cast(
            list[StringValue],
            [arg.accept(self) for arg in node.args],
        )

        name = node.callee.name

        if name == "starts_with":
            return BooleanValue(expr.value.startswith(args[0].value))

        if name == "ends_with":
            return BooleanValue(expr.value.endswith(args[0].value))

        if name == "strip":
            return StringValue(expr.value.strip())

        assert False

    def visit_title_stmt(self, node: TitleStatement) -> Value:
        # TitleStatement is special in that it is used for display purposes and
        # is computed after semantic analysis, but before the actual evaluation
        # of the workflow.
        return UnitValue()

    def visit_func_def_stmt(self, node: FunctionDefStatement) -> Value:
        self.symbols[node.name] = FunctionValue(type=node.type, func=node)

        return UnitValue()

    @contextmanager
    def new_scope(self) -> Iterator[None]:
        self.symbols = self.symbols.new_child()

        yield

        self.symbols = self.symbols.parents

    def reassign_variable(self, name: str, value: Value) -> None:
        """
        Reassign an identifier in a previous scope without creating a new
        scope. This is useful for reassigning values that are defined in scopes
        above the current scope. If the name does not exist in the symbol table
        whatsoever, an exception is thrown.
        """

        for symbols in self.symbols.maps:
            if name in symbols:
                symbols[name] = value

                return

        raise KeyError(  # pragma: no cover
            f"Cannot reassign `{name}` because it doesn't exist"
        )

    def get_fullname(self, node: Expression) -> str:
        if isinstance(node, IdentifierExpression):
            return node.name

        if isinstance(node, MemberExpression):
            lhs = self.get_fullname(node.lhs)

            return f"{lhs}.{node.name}"

        assert False


def eval_title(title: TitleStatement | None) -> str | None:
    if not title:
        return None

    visitor = ConstexprEvalVisitor()

    parts = [value_to_string(x.accept(visitor)) for x in title.parts]

    assert all(isinstance(x, StringValue) for x in parts)

    return " ".join(x.value for x in parts)  # type: ignore
