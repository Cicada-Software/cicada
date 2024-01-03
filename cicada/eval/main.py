import asyncio
import sys
from inspect import isawaitable
from pathlib import Path
from typing import cast

from cicada.api.settings import trigger_from_env
from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import SHELL_ALIASES, AstError
from cicada.ast.nodes import (
    CacheStatement,
    Expression,
    FunctionDefStatement,
    FunctionExpression,
    FunctionValue,
    IdentifierExpression,
    MemberExpression,
    RecordValue,
    UnitValue,
    UnreachableValue,
    Value,
)
from cicada.ast.semantic_analysis import IgnoreWorkflow, StringCoercibleType
from cicada.ast.types import FunctionType, RecordType, StringType, UnitType, VariadicTypeArg
from cicada.domain.triggers import Trigger
from cicada.eval.builtins import builtin_print, builtin_shell, hashOf
from cicada.eval.constexpr_visitor import ConstexprEvalVisitor
from cicada.eval.find_files import find_ci_files

# TODO: deduplicate this
BUILT_IN_SYMBOLS: dict[str, Value] = {
    "shell": FunctionValue(
        type=FunctionType([VariadicTypeArg(StringCoercibleType)], rtype=RecordType()),
        func=builtin_shell,
    ),
    "print": FunctionValue(
        FunctionType(
            [VariadicTypeArg(StringCoercibleType)],
            rtype=UnitType(),
        ),
        func=builtin_print,
    ),
    "hashOf": FunctionValue(
        FunctionType(
            [StringType(), VariadicTypeArg(StringType())],
            rtype=StringType(),
        ),
        func=hashOf,
    ),
    **{
        alias: FunctionValue(
            FunctionType([StringCoercibleType], rtype=RecordType()),
            func=builtin_shell,
        )
        for alias in SHELL_ALIASES
    },
}


class EvalVisitor(ConstexprEvalVisitor):
    cached_files: list[Path] | None
    cache_key: str | None

    def __init__(self, trigger: Trigger | None = None) -> None:
        super().__init__(trigger)
        self.symbols.update(BUILT_IN_SYMBOLS.copy())
        self.symbols = self.symbols.new_child()

        self.cached_files = None
        self.cache_key = None

    async def visit_func_expr(self, node: FunctionExpression) -> Value:
        if (expr := await super().visit_func_expr(node)) is not NotImplemented:
            return expr

        assert isinstance(node.callee, IdentifierExpression | MemberExpression)

        symbol = self.get_symbol(node.callee)

        if not symbol:
            return UnreachableValue()

        assert isinstance(symbol, FunctionValue)

        if isinstance(symbol.func, FunctionDefStatement):
            func = symbol.func

            with self.new_scope():
                args = [await arg.accept(self) for arg in node.args]

                for name, arg in zip(func.arg_names, args, strict=True):
                    self.symbols[name] = arg

                rvalue = await func.body.accept(self)

                return UnitValue() if symbol.type.rtype == UnitType() else rvalue

        if callable(symbol.func):
            # TODO: make this type-safe
            f = symbol.func(self, node)

            if isawaitable(f):
                return cast(Value, await f)

            return cast(Value, f)

        return UnreachableValue()

    async def visit_cache_stmt(self, node: CacheStatement) -> Value:
        print("Caching is not yet supported for locally ran workflows")  # noqa: T201

        return UnitValue()

    def get_symbol(self, node: Expression) -> Value | None:
        if isinstance(node, IdentifierExpression):
            return self.symbols.get(node.name)

        if isinstance(node, MemberExpression):
            if lhs := self.get_symbol(node.lhs):
                if isinstance(lhs, RecordValue):
                    return lhs.value.get(node.name)

        return None


async def run_pipeline(
    contents: str,
    filename: str | None = None,
    trigger: Trigger | None = None,
) -> None:
    try:
        trigger = trigger or trigger_from_env()

        tree = await parse_and_analyze(contents, trigger, file_root=Path.cwd())

        await tree.accept(EvalVisitor(trigger))

    except IgnoreWorkflow:
        pass

    except AstError as ex:  # pragma: no cover
        ex.filename = ex.filename or filename

        print(ex)  # noqa: T201


def main(filenames: list[str]) -> None:  # pragma: no cover
    files = [Path(x) for x in filenames]

    for file in files or find_ci_files(Path.cwd()):
        asyncio.run(run_pipeline(file.read_text(), filename=str(file)))


if __name__ == "__main__":
    main(sys.argv[1:])  # pragma: no cover
