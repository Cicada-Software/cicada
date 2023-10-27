from collections import ChainMap
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import cast

from cicada.ast.common import trigger_to_record
from cicada.ast.generate import SHELL_ALIASES, AstError
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanValue,
    CacheStatement,
    Expression,
    FileNode,
    FunctionAnnotation,
    FunctionDefStatement,
    FunctionExpression,
    FunctionValue,
    IdentifierExpression,
    IfExpression,
    LetExpression,
    ListExpression,
    MemberExpression,
    NumericValue,
    OnStatement,
    ParenthesisExpression,
    RecordValue,
    RunOnStatement,
    ShellEscapeExpression,
    StringValue,
    TitleStatement,
    ToStringExpression,
    TraversalVisitor,
    UnaryExpression,
    UnaryOperator,
    Value,
)
from cicada.ast.types import (
    BOOL_LIKE_TYPES,
    BooleanType,
    CommandType,
    FunctionType,
    ListType,
    NumericType,
    RecordType,
    StringType,
    Type,
    UnionType,
    UnitType,
    UnknownType,
    VariadicTypeArg,
)
from cicada.domain.triggers import Trigger


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
    BinaryOperator.IS_NOT: [Type],
    BinaryOperator.ASSIGN: [Type],
    BinaryOperator.IN: [StringType],
    BinaryOperator.NOT_IN: [StringType],
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
    BinaryOperator.IS_NOT: BooleanType,
    BinaryOperator.IN: BooleanType,
    BinaryOperator.NOT_IN: BooleanType,
}


# TODO: combine with bool like types in types.py
STRING_COERCIBLE_TYPES: tuple[Type, ...] = (
    StringType(),
    BooleanType(),
    NumericType(),
)

StringCoercibleType = UnionType(STRING_COERCIBLE_TYPES)


RESERVED_NAMES = {"event", "env", "secret"}


Symbol = Value | Expression


# TODO: make sure this immutable
BUILT_IN_SYMBOLS: dict[str, Symbol] = {
    "shell": FunctionValue(
        FunctionType([VariadicTypeArg(StringCoercibleType)], rtype=CommandType()),
    ),
    "print": FunctionValue(
        FunctionType(
            [VariadicTypeArg(StringCoercibleType)],
            rtype=UnitType(),
        ),
    ),
    "hashOf": FunctionValue(
        FunctionType([StringType(), VariadicTypeArg(StringType())], rtype=StringType()),
    ),
    **{
        alias: FunctionValue(FunctionType([StringCoercibleType], rtype=CommandType()))
        for alias in SHELL_ALIASES
    },
}

# Function annotations are not first-class objects, meaning they cannot be used
# outside of annotations. This also means you can declare a symbol with the
# same name as an annotation and the name will still be reserved for the
# annotation. These semantics will be merged in the future.
BUILT_IN_ANNOTATIONS = ("workflow",)


MEMBER_FUNCTION_TYPES: dict[str, tuple[Type, Symbol]] = {
    "starts_with": (
        StringType(),
        FunctionValue(FunctionType([StringType()], rtype=BooleanType())),
    ),
    "ends_with": (
        StringType(),
        FunctionValue(FunctionType([StringType()], rtype=BooleanType())),
    ),
    "strip": (
        StringType(),
        FunctionValue(FunctionType([], rtype=StringType())),
    ),
}


class SemanticAnalysisVisitor(TraversalVisitor):
    types: dict[str, Type]
    symbols: ChainMap[str, Symbol]
    trigger: Trigger | None

    # This is set when a function has been called, used to detect non-constexpr
    # functions being called before an `on` statement. There is probably a more
    # elegant way of detecting this, for example, adding a constexpr flag to
    # each statement node.
    has_ran_function: bool

    # Set whenever an `on` statement is found, used to detect if there are
    # multiple on statements defined.
    has_on_stmt: bool

    # Set whenever a `cache` statement is found as there cannot be multiple
    # cache statements in a single file.
    cache_stmt: CacheStatement | None

    run_on: RunOnStatement | None

    file_node: FileNode | None = None

    def __init__(self, trigger: Trigger | None = None) -> None:
        self.symbols = ChainMap(BUILT_IN_SYMBOLS.copy())
        self.trigger = trigger
        self.has_ran_function = False
        self.has_on_stmt = False
        self.run_on = None
        self.file_node = None
        self.cache_stmt = None

        if self.trigger:
            event = cast(RecordValue, trigger_to_record(self.trigger))

            self.symbols["event"] = event
            self.symbols["env"] = event.value["env"]
            self.symbols["secret"] = event.value["secret"]

    def visit_file_node(self, node: FileNode) -> None:
        self.file_node = node

        super().visit_file_node(node)

    def visit_let_expr(self, node: LetExpression) -> None:
        super().visit_let_expr(node)

        if node.name in RESERVED_NAMES:
            raise AstError(f"Name `{node.name}` is reserved", node)

        self.symbols[node.name] = node

        if self.is_constexpr(node.expr):
            node.is_constexpr = True

        node.type = node.expr.type

    def visit_member_expr(self, node: MemberExpression) -> None:
        super().visit_member_expr(node)

        if isinstance(node.lhs.type, RecordType):
            for name, field_type in node.lhs.type.fields.items():
                if name == node.name:
                    node.type = field_type
                    break

            else:
                name = cast(IdentifierExpression, node.lhs).name

                raise AstError(
                    f"Member `{node.name}` does not exist on `{name}`",
                    node,
                )

        elif isinstance(node.lhs, IdentifierExpression | MemberExpression) and (
            data := MEMBER_FUNCTION_TYPES.get(node.name)
        ):
            node.type = data[1].type

        else:
            name = cast(IdentifierExpression, node.lhs).name

            raise AstError(
                f"Member `{node.name}` does not exist on `{name}`",
                node,
            )

        if self.is_constexpr(node.lhs):
            node.is_constexpr = True

    def visit_ident_expr(self, node: IdentifierExpression) -> None:
        super().visit_ident_expr(node)

        if symbol := self.symbols.get(node.name):
            node.type = symbol.type

        else:
            raise AstError(f"Variable `{node.name}` is not defined", node)

    def visit_paren_expr(self, node: ParenthesisExpression) -> None:
        # TODO: test this

        super().visit_paren_expr(node)

        node.type = node.expr.type

    def visit_list_expr(self, node: ListExpression) -> None:
        super().visit_list_expr(node)

        inner_type: Type = UnknownType()

        if node.items:
            # TODO: gather types into a union type instead

            inner_type = node.items[0].type

            for item in node.items:
                if item.type != inner_type:
                    raise AstError(
                        f"Expected type `{inner_type}`, got type `{item.type}` instead",
                        item,
                    )

        node.type = ListType(inner_type)
        node.is_constexpr = all(item.is_constexpr for item in node.items)

    def visit_unary_expr(self, node: UnaryExpression) -> None:
        super().visit_unary_expr(node)

        if node.oper == UnaryOperator.NOT:
            if node.rhs.type != BooleanType():
                raise AstError(
                    "Cannot use `not` operator with non-boolean value",
                    node,
                )

        elif node.oper == UnaryOperator.NEGATE:
            if node.rhs.type != NumericType():
                raise AstError("Cannot use `-` operator with non-numeric value", node)

        else:
            assert False

        if self.is_constexpr(node.rhs):
            node.is_constexpr = True

    def visit_binary_expr(self, node: BinaryExpression) -> None:
        node.rhs.accept(self)

        if node.oper == BinaryOperator.ASSIGN:
            if isinstance(node.lhs, IdentifierExpression):
                node.lhs.accept(self)

                var = self.get_symbol(node.lhs)

                if isinstance(var, LetExpression) and not var.is_mutable:
                    raise AstError(
                        f"Cannot assign to immutable variable `{node.lhs.name}` (are you forgetting `mut`?)",  # noqa: E501
                        node.lhs,
                    )

            elif isinstance(node.lhs, MemberExpression):
                member = node.lhs

                member.lhs.accept(self)

                rvalue = self.get_symbol(member.lhs)

                assert isinstance(rvalue, RecordValue)
                assert isinstance(rvalue.type, RecordType)

                match member.lhs:
                    case IdentifierExpression(name="event"):
                        raise AstError(
                            "Cannot reassign `event` because it is immutable",
                            node.rhs,
                        )

                if rvalue.type.fields.get(member.name):
                    member.accept(self)

                    self.ensure_valid_op_types(
                        member,
                        node.oper,
                        node.rhs,
                    )

                else:
                    # TODO: Should we be able to assign arbitrary values to
                    # records? I feel like this shouldn't be allowed, but for
                    # env vars it has to.

                    match member.lhs:
                        case IdentifierExpression(name="env"):
                            if node.rhs.type != StringType():
                                # TODO: add more info here
                                msg = "You can only assign strings to env vars"

                                raise AstError(msg, node.rhs)

                    # TODO: RecordType should be immutable, but it's easier
                    # to just assign directly.
                    rvalue.type.fields[member.name] = node.rhs.type

                    member.accept(self)

            else:
                raise AstError("You can only assign to variables", node.lhs)

        else:
            node.lhs.accept(self)

        self.ensure_valid_op_types(node.lhs, node.oper, node.rhs)

        allowed_types = OPERATOR_ALLOWED_TYPES[node.oper]

        if Type not in allowed_types and type(node.lhs.type) not in allowed_types:
            # TODO: move to AstError class
            wrapped = [f"`{ty()}`" for ty in allowed_types]

            if len(wrapped) > 1:
                wrapped[-1] = f"or {wrapped[-1]}"

            types = ", ".join(wrapped)

            raise AstError(
                f"Expected type {types}, got type `{node.lhs.type}` instead",
                node.lhs,
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

        if not isinstance(node.callee, IdentifierExpression):
            if not isinstance(node.callee, MemberExpression):
                raise NotImplementedError

            member_type, symbol = MEMBER_FUNCTION_TYPES[node.callee.name]

            assert isinstance(symbol, FunctionValue)

            if node.callee.lhs.type != member_type:
                ty = node.callee.lhs.type

                raise AstError(
                    f"Expected type `{member_type}`, got type `{ty}` instead",
                    node.callee.lhs,
                )

            if len(node.args) != len(symbol.type.arg_types):
                raise AstError.incorrect_arg_count(
                    func_name=node.callee.name,
                    expected=len(symbol.type.arg_types),
                    got=len(node.args),
                    info=node,
                )

            for arg, arg_type in zip(node.args, symbol.type.arg_types, strict=True):
                if arg.type != arg_type:
                    raise AstError(
                        f"Expected type `{arg_type}`, got type `{arg.type}` instead",
                        arg,
                    )

            node.type = symbol.type.rtype

            node.is_constexpr = self.is_constexpr(node.callee) and all(
                self.is_constexpr(x) for x in node.args
            )

            return

        symbol = self.symbols.get(node.callee.name)  # type: ignore

        # TODO: this is never hit because callee is always checked
        if not symbol:
            raise AstError(
                f"Function `{node.callee.name}` is not defined",
                node,
            )

        assert isinstance(symbol, FunctionValue)

        func_arg_types = symbol.type.arg_types

        is_variadic = func_arg_types and isinstance(func_arg_types[-1], VariadicTypeArg)

        # Ensure only the last func arg is variadic. This should always be true
        assert not any(isinstance(arg, VariadicTypeArg) for arg in func_arg_types[:-1])

        if is_variadic:
            self.type_check_variadic_func_expr(node, symbol)

        else:
            self.type_check_normal_func_expr(node, symbol)

        self.has_ran_function = True
        node.type = symbol.type.rtype

    def type_check_variadic_func_expr(
        self,
        node: FunctionExpression,
        symbol: FunctionValue,
    ) -> None:
        assert isinstance(node.callee, IdentifierExpression)

        required_args = len(symbol.type.arg_types) - 1

        positionals = node.args[:required_args]
        variadics = node.args[required_args:]

        if len(positionals) < required_args:
            raise AstError.incorrect_arg_count(
                func_name=node.callee.name,
                expected=required_args,
                got=len(positionals),
                info=node,
                at_least=True,
            )

        for arg, ty in zip(positionals, symbol.type.arg_types, strict=False):
            if not self.is_type_compatible(arg.type, ty):
                raise AstError(
                    f"Expected type `{ty}`, got type `{arg.type}` instead",
                    arg.info,
                )

        for arg in variadics:
            var_arg = symbol.type.arg_types[-1]
            assert isinstance(var_arg, VariadicTypeArg)

            if not self.is_type_compatible(arg.type, var_arg.type):
                msg = f"Expected type `{var_arg.type}`, got type `{arg.type}` instead"

                raise AstError(msg, arg)

    def type_check_normal_func_expr(self, node: FunctionExpression, symbol: FunctionValue) -> None:
        assert isinstance(node.callee, IdentifierExpression)

        expected = len(symbol.type.arg_types)
        got = len(node.args)

        if expected != got:
            raise AstError.incorrect_arg_count(
                func_name=node.callee.name,
                expected=expected,
                got=got,
                info=node,
            )

        for arg, ty in zip(node.args, symbol.type.arg_types, strict=True):
            if not self.is_type_compatible(arg.type, ty):
                raise AstError(
                    f"Expected type `{ty}`, got type `{arg.type}` instead",
                    arg,
                )

    def visit_on_stmt(self, node: OnStatement) -> None:
        if self.has_on_stmt:
            # TODO: include location of existing on stmt

            raise AstError(
                "Cannot use multiple `on` statements in a single file",
                node,
            )

        if self.has_ran_function:
            # TODO: include location of offending non-constexpr function

            raise AstError("Cannot use `on` statement after a function call", node)

        super().visit_on_stmt(node)

        if not self.trigger:
            raise AstError(
                "Cannot use `on` statement when trigger is not defined",
                node,
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
                    node.where,
                )

            if node.where.type != BooleanType():
                raise AstError(
                    "`where` clause must be a boolean type",
                    node.where,
                )

        self.has_on_stmt = True

    def visit_run_on_stmt(self, node: RunOnStatement) -> None:
        super().visit_run_on_stmt(node)

        if self.has_ran_function:
            raise AstError(
                "Cannot use `run_on` statement after a function call",
                node,
            )

        if self.run_on:
            raise AstError(
                "Cannot use multiple `run_on` statements in a single file",
                node,
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
                    f"Type `{node.condition.type}` cannot be converted to bool",
                    node.condition,
                )

            node.is_constexpr = node.body.is_constexpr
            node.type = UnionType((node.body.type, UnknownType()))

    def visit_block_expr(self, node: BlockExpression) -> None:
        super().visit_block_expr(node)

        if not node.exprs:  # pragma: no cover
            raise AstError("Block cannot be empty", node)

        node.is_constexpr = all(self.is_constexpr(x) for x in node.exprs)
        node.type = node.exprs[-1].type

    def visit_to_string_expr(self, node: ToStringExpression) -> None:
        super().visit_to_string_expr(node)

        if node.expr.type not in STRING_COERCIBLE_TYPES:
            raise AstError(
                f"Cannot convert type `{node.expr.type}` to `{StringType()}`",
                node.expr,
            )

        node.type = StringType()

    def visit_shell_escape_expr(self, node: ShellEscapeExpression) -> None:
        super().visit_shell_escape_expr(node)

        if node.expr.type != StringType():
            raise AstError(
                f"Expected `{StringType()}` type, got type `{node.expr.type}`",
                node.expr,
            )

        node.type = StringType()

    def visit_cache_stmt(self, node: CacheStatement) -> None:
        super().visit_cache_stmt(node)

        if self.cache_stmt:
            msg = "Cannot have multiple `cache` statements in a single file"

            raise AstError(msg, node)

        if node.using.type != StringType():
            raise AstError(
                f"Expected `{StringType()}` type, got type `{node.using.type}`",
                node.using,
            )

        self.cache_stmt = node

    def visit_title_stmt(self, node: TitleStatement) -> None:
        super().visit_title_stmt(node)

        if self.file_node and self.file_node.title:
            raise AstError(
                "Cannot have multiple `title` statements in a single file",
                node,
            )

        for part in node.parts:
            if not part.is_constexpr:
                raise AstError(  # pragma: no cover
                    "Only constant values allowed in `title`",
                    part,
                )

        if self.file_node:
            self.file_node.title = node

    def visit_func_def_stmt(self, node: FunctionDefStatement) -> None:
        # TODO: only allow funcs at top level for now?
        # TODO: allow calling user defined functions via shell format

        self.symbols[node.name] = FunctionValue(type=node.type, func=node)

        self.check_for_duplicate_arg_names(node)

        with self.new_scope():
            for arg, ty in zip(node.arg_names, node.type.arg_types, strict=True):
                # TODO: this should be just a type since the value is unknown

                if ty == StringType():
                    value: Value = StringValue("")
                elif ty == NumericType():
                    value = NumericValue(Decimal(0))
                elif ty == BooleanType():
                    value = BooleanValue(False)
                else:
                    assert False

                self.symbols[arg] = value

            super().visit_func_def_stmt(node)

        func_rtype = node.type.rtype
        body_rtype = node.body.exprs[-1].type

        if func_rtype != UnitType() and body_rtype != func_rtype:
            raise AstError(
                f"Expected type `{func_rtype}`, got type `{body_rtype}` instead",
                node.body.exprs[-1],
            )

    def visit_func_annotation(self, node: FunctionAnnotation) -> None:
        if node.expr.name not in BUILT_IN_ANNOTATIONS:
            raise AstError(
                f"Unknown annotation `@{node.expr.name}`",
                node.expr,
            )

    @staticmethod
    def check_for_duplicate_arg_names(node: FunctionDefStatement) -> None:
        seen = set[str]()

        for arg_name in node.arg_names:
            if arg_name in seen:
                # TODO: use identifier exprs as arg names so we can have line
                # and column info
                raise AstError(
                    f"Argument `{arg_name}` already exists",
                    node,
                )

            seen.add(arg_name)

    @contextmanager
    def new_scope(self) -> Iterator[None]:
        self.symbols = self.symbols.new_child()

        yield

        self.symbols = self.symbols.parents

    def is_constexpr(self, node: Expression) -> bool:
        if isinstance(node, IdentifierExpression):
            if symbol := self.symbols.get(node.name):
                if isinstance(symbol, Expression):
                    return symbol.is_constexpr

            if node.name in RESERVED_NAMES:
                return True

            return False

        return node.is_constexpr

    @staticmethod
    def ensure_valid_op_types(lhs: Expression, oper: BinaryOperator, rhs: Expression) -> None:
        if lhs.type != rhs.type:
            verb = "assigned to" if oper == BinaryOperator.ASSIGN else "used with"

            raise AstError(
                f"Expression of type `{rhs.type}` cannot be {verb} type `{lhs.type}`",
                rhs,
            )

    def get_symbol(self, node: Expression) -> Expression | Value | None:
        if isinstance(node, IdentifierExpression):
            return self.symbols.get(node.name)

        if isinstance(node, MemberExpression):
            if lhs := self.get_symbol(node.lhs):
                if isinstance(lhs, RecordValue):
                    return lhs.value.get(node.name)

        return None

    @staticmethod
    def is_type_compatible(compare: Type, to: Type) -> bool:
        if isinstance(to, UnionType):
            return compare in to.types

        return compare == to
