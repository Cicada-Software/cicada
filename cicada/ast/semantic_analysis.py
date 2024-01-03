from collections import ChainMap
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import cast

from cicada.ast.common import trigger_to_record
from cicada.ast.generate import SHELL_ALIASES, AstError, generate_ast_tree
from cicada.ast.nodes import (
    BinaryExpression,
    BinaryOperator,
    BlockExpression,
    BooleanValue,
    CacheStatement,
    ElifExpression,
    Expression,
    FileNode,
    ForStatement,
    FunctionAnnotation,
    FunctionDefStatement,
    FunctionExpression,
    FunctionValue,
    IdentifierExpression,
    IfExpression,
    ImportStatement,
    LetExpression,
    ListExpression,
    MemberExpression,
    ModuleValue,
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
    ModuleType,
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
from cicada.parse.tokenize import tokenize


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

    loaded_modules: dict[Path, FileNode]

    file_root: Path | None = None

    def __init__(self, trigger: Trigger | None = None, file_root: Path | None = None) -> None:
        # Load builtin symbols into symbol table
        self.symbols = ChainMap(BUILT_IN_SYMBOLS.copy())
        # Create a new scope so that builtin symbols can be differentiated from user defined ones
        self.symbols = self.symbols.new_child()
        self.trigger = trigger
        self.has_ran_function = False
        self.has_on_stmt = False
        self.run_on = None
        self.file_node = None
        self.cache_stmt = None
        self.loaded_modules = {}
        self.is_inside_import = False

        if file_root:
            assert file_root.is_absolute()
            self.file_root = file_root

        if self.trigger:
            event = cast(RecordValue, trigger_to_record(self.trigger))

            self.symbols["event"] = event
            self.symbols["env"] = event.value["env"]
            self.symbols["secret"] = event.value["secret"]

    async def visit_file_node(self, node: FileNode) -> None:
        self.file_node = node

        await super().visit_file_node(node)

    async def visit_let_expr(self, node: LetExpression) -> None:
        await super().visit_let_expr(node)

        if node.name in RESERVED_NAMES:
            raise AstError(f"Name `{node.name}` is reserved", node)

        self.symbols[node.name] = node

        if self.is_constexpr(node.expr):
            node.is_constexpr = True

        node.type = node.expr.type

    async def visit_member_expr(self, node: MemberExpression) -> None:
        await super().visit_member_expr(node)

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

    async def visit_ident_expr(self, node: IdentifierExpression) -> None:
        await super().visit_ident_expr(node)

        if symbol := self.symbols.get(node.name):
            node.type = symbol.type

        else:
            raise AstError(f"Variable `{node.name}` is not defined", node)

    async def visit_paren_expr(self, node: ParenthesisExpression) -> None:
        # TODO: test this

        await super().visit_paren_expr(node)

        node.type = node.expr.type

    async def visit_list_expr(self, node: ListExpression) -> None:
        await super().visit_list_expr(node)

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

    async def visit_unary_expr(self, node: UnaryExpression) -> None:
        await super().visit_unary_expr(node)

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

    async def visit_binary_expr(self, node: BinaryExpression) -> None:
        await node.rhs.accept(self)

        if node.oper == BinaryOperator.ASSIGN:
            if isinstance(node.lhs, IdentifierExpression):
                await node.lhs.accept(self)

                var = self.get_symbol(node.lhs)

                if isinstance(var, LetExpression) and not var.is_mutable:
                    raise AstError(
                        f"Cannot assign to immutable variable `{node.lhs.name}` (are you forgetting `mut`?)",  # noqa: E501
                        node.lhs,
                    )

            elif isinstance(node.lhs, MemberExpression):
                member = node.lhs

                await member.lhs.accept(self)

                rvalue = self.get_symbol(member.lhs)

                assert isinstance(rvalue, RecordValue)
                assert isinstance(rvalue.type, RecordType)

                match member.lhs:
                    case IdentifierExpression(name="event"):
                        raise AstError(
                            "Cannot reassign `event` because it is immutable",
                            node.rhs,
                        )

                if sym := rvalue.value.get(member.name):
                    # TODO: better encapsulate what is assignable or not
                    # TODO: include lhs of member expr in error

                    lhs = rvalue.type.name if isinstance(rvalue, ModuleValue) else ""

                    match sym:
                        case LetExpression(is_mutable=False):
                            raise AstError(
                                f"Cannot reassign `{lhs}.{member.name}` because it is immutable",
                                sym,
                            )

                    await member.accept(self)

                    self.ensure_valid_op_types(member, node.oper, node.rhs)

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

                    await member.accept(self)

            else:
                raise AstError("You can only assign to variables", node.lhs)

        else:
            await node.lhs.accept(self)

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

    async def visit_func_expr(self, node: FunctionExpression) -> None:
        await super().visit_func_expr(node)

        if not isinstance(node.callee, IdentifierExpression):
            if not isinstance(node.callee, MemberExpression):
                raise NotImplementedError

            if data := MEMBER_FUNCTION_TYPES.get(node.callee.name):
                member_type, symbol = data

                if node.callee.lhs.type != member_type:
                    ty = node.callee.lhs.type

                    raise AstError(
                        f"Expected type `{member_type}`, got type `{ty}` instead",
                        node.callee.lhs,
                    )

            else:
                lhs = self.get_symbol(node.callee.lhs)

                assert isinstance(lhs, RecordValue)

                symbol = lhs.value[node.callee.name]
                member_type = symbol.type

            assert isinstance(symbol, FunctionValue)

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

        self.check_no_subworkflows_in_imported_modules(node, symbol)

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

    def check_no_subworkflows_in_imported_modules(
        self, node: FunctionExpression, symbol: FunctionValue
    ) -> None:
        if not self.is_inside_import:
            return

        assert symbol.func

        if not isinstance(symbol.func, FunctionDefStatement):
            return

        for annotation in symbol.func.annotations:
            match annotation:
                case FunctionAnnotation(IdentifierExpression("workflow")):
                    raise AstError("Cannot create sub-workflow in imported modules", node)

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

    async def visit_on_stmt(self, node: OnStatement) -> None:
        if self.has_on_stmt:
            # TODO: include location of existing on stmt

            raise AstError(
                "Cannot use multiple `on` statements in a single file",
                node,
            )

        if self.has_ran_function:
            # TODO: include location of offending non-constexpr function

            raise AstError("Cannot use `on` statement after a function call", node)

        if self.is_inside_import:
            raise AstError("Cannot use `on` inside imported modules", node)

        await super().visit_on_stmt(node)

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

    async def visit_run_on_stmt(self, node: RunOnStatement) -> None:
        await super().visit_run_on_stmt(node)

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

        if self.is_inside_import:
            raise AstError("Cannot use `run_on` inside imported modules", node)

        # TODO: use run_on field from field_node instead
        self.run_on = node

        if self.file_node:
            self.file_node.run_on = node

    async def visit_if_expr(self, node: IfExpression) -> None:
        with self.new_scope():
            await node.condition.accept(self)
            await node.body.accept(self)

            if node.condition.type not in BOOL_LIKE_TYPES:
                raise AstError(
                    f"Type `{node.condition.type}` cannot be converted to bool",
                    node.condition,
                )

        for _elif in node.elifs:
            await _elif.accept(self)

        if node.else_block:
            with self.new_scope():
                await node.else_block.accept(self)

        node.is_constexpr = (
            node.body.is_constexpr
            and all(x.is_constexpr for x in node.elifs)
            and (node.else_block.is_constexpr if node.else_block else True)
        )

        elif_types = [x.type for x in node.elifs]

        # TODO: should unit type be used instead of unknown type?
        else_type = node.else_block.type if node.else_block else UnknownType()

        node.type = UnionType.union_or_single((node.body.type, *elif_types, else_type))

    async def visit_elif_expr(self, node: ElifExpression) -> None:
        with self.new_scope():
            await super().visit_elif_expr(node)

            if node.condition.type not in BOOL_LIKE_TYPES:
                raise AstError(
                    f"Type `{node.condition.type}` cannot be converted to bool",
                    node.condition,
                )

            node.is_constexpr = node.body.is_constexpr
            node.type = node.body.type

    async def visit_block_expr(self, node: BlockExpression) -> None:
        await super().visit_block_expr(node)

        if not node.exprs:  # pragma: no cover
            raise AstError("Block cannot be empty", node)

        node.is_constexpr = all(self.is_constexpr(x) for x in node.exprs)
        node.type = node.exprs[-1].type

    async def visit_to_string_expr(self, node: ToStringExpression) -> None:
        await super().visit_to_string_expr(node)

        if node.expr.type not in STRING_COERCIBLE_TYPES:
            raise AstError(
                f"Cannot convert type `{node.expr.type}` to `{StringType()}`",
                node.expr,
            )

        node.type = StringType()

    async def visit_shell_escape_expr(self, node: ShellEscapeExpression) -> None:
        await super().visit_shell_escape_expr(node)

        if node.expr.type != StringType():
            raise AstError(
                f"Expected `{StringType()}` type, got type `{node.expr.type}`",
                node.expr,
            )

        node.type = StringType()

    async def visit_cache_stmt(self, node: CacheStatement) -> None:
        await super().visit_cache_stmt(node)

        if self.cache_stmt:
            raise AstError("Cannot have multiple `cache` statements in a single file", node)

        if self.is_inside_import:
            raise AstError("Cannot use `cache` inside imported modules", node)

        if node.using.type != StringType():
            raise AstError(
                f"Expected `{StringType()}` type, got type `{node.using.type}`",
                node.using,
            )

        self.cache_stmt = node

    async def visit_title_stmt(self, node: TitleStatement) -> None:
        await super().visit_title_stmt(node)

        if self.file_node and self.file_node.title:
            raise AstError(
                "Cannot have multiple `title` statements in a single file",
                node,
            )

        if self.is_inside_import:
            raise AstError("Cannot use `title` inside imported modules", node)

        for part in node.parts:
            if not part.is_constexpr:
                raise AstError(  # pragma: no cover
                    "Only constant values allowed in `title`",
                    part,
                )

        if self.file_node:
            self.file_node.title = node

    async def visit_func_def_stmt(self, node: FunctionDefStatement) -> None:
        # TODO: only allow funcs at top level for now?
        # TODO: allow calling user defined functions via shell format

        self.symbols[node.name] = FunctionValue(type=node.type, func=node)

        self.check_for_duplicate_arg_names(node)
        self.check_annotation_types(node)

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

            await super().visit_func_def_stmt(node)

        func_rtype = node.type.rtype
        body_rtype = node.body.exprs[-1].type

        if func_rtype != UnitType() and body_rtype != func_rtype:
            raise AstError(
                f"Expected type `{func_rtype}`, got type `{body_rtype}` instead",
                node.body.exprs[-1],
            )

    async def visit_func_annotation(self, node: FunctionAnnotation) -> None:
        if node.expr.name not in BUILT_IN_ANNOTATIONS:
            raise AstError(
                f"Unknown annotation `@{node.expr.name}`",
                node.expr,
            )

    async def visit_for_stmt(self, node: ForStatement) -> None:
        await node.source.accept(self)

        if not isinstance(node.source.type, ListType):
            raise AstError(
                f"Expected list type, got type `{node.source.type}` instead",
                node.source,
            )

        if node.source.type.inner_type == UnknownType():
            raise AstError(
                f"Cannot iterate over value of type `{node.source.type}`. Is it empty?",
                node.name,
            )

        with self.new_scope():
            self.symbols[node.name.name] = node.name

            node.name.type = node.source.type.inner_type

            await node.body.accept(self)

    async def visit_import_stmt(self, node: ImportStatement) -> None:
        # Require a file root for doing any imports since we need to know where files should be
        # imported from.
        assert self.file_root

        node.full_path = (self.file_root / node.module).resolve()

        if not node.full_path.is_relative_to(self.file_root):
            raise AstError("Cannot import files outside of root directory", node)

        if tree := self.loaded_modules.get(node.full_path):
            node.tree = tree
            return

        module_name = node.module.stem

        if self.symbols.get(module_name):
            raise AstError(
                f"Cannot import `{node.module}`: Importing `{module_name}` would shadow existing variable/function",  # noqa: E501
                node,
            )

        if not node.full_path.name.endswith(".ci"):
            raise AstError(
                f"Cannot import `{node.module}`: Imported files must end in `.ci`",
                node,
            )

        if not node.full_path.exists():
            raise AstError(f"Cannot import `{node.module}`: File does not exist", node)

        code = node.full_path.read_text()

        tokens = tokenize(code)
        node.tree = generate_ast_tree(tokens)

        self.loaded_modules[node.full_path] = node.tree

        try:
            module_visitor = SemanticAnalysisVisitor(trigger=None, file_root=self.file_root)
            module_visitor.loaded_modules = self.loaded_modules
            module_visitor.is_inside_import = True

            await node.tree.accept(module_visitor)

            # TODO: turn this into a function
            record_type = ModuleType(name=module_name)
            record_values = {}

            symbols: dict[str, Value] = dict(*module_visitor.symbols.maps[:1])

            for name, symbol in symbols.items():
                record_type.fields[name] = symbol.type
                record_values[name] = symbol

            self.symbols[module_name] = ModuleValue(record_values, record_type)

        except AstError as ex:
            ex.filename = str(node.module)
            raise

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

    @staticmethod
    def check_annotation_types(node: FunctionDefStatement) -> None:
        match node.annotations:
            case [FunctionAnnotation(IdentifierExpression("workflow"))]:
                if node.type.rtype != UnitType():
                    raise AstError(
                        "`@workflow` annotated functions must have `()` return type",
                        node,
                    )

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
