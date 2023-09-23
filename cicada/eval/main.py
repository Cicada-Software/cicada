import sys
from pathlib import Path

from cicada.api.settings import trigger_from_env
from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import SHELL_ALIASES, AstError
from cicada.ast.nodes import (
    CacheStatement,
    FunctionDefStatement,
    FunctionExpression,
    FunctionValue,
    IdentifierExpression,
    UnitValue,
    UnreachableValue,
    Value,
)
from cicada.ast.semantic_analysis import IgnoreWorkflow, StringCoercibleType
from cicada.ast.types import (
    FunctionType,
    RecordType,
    StringType,
    UnitType,
    VariadicTypeArg,
)
from cicada.domain.triggers import Trigger
from cicada.eval.builtins import builtin_print, builtin_shell, hashOf
from cicada.eval.constexpr_visitor import ConstexprEvalVisitor
from cicada.eval.find_files import find_ci_files

# TODO: deduplicate this
BUILT_IN_SYMBOLS: dict[str, Value] = {
    "shell": FunctionValue(
        type=FunctionType(
            [VariadicTypeArg(StringCoercibleType)], rtype=RecordType()
        ),
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

        self.cached_files = None
        self.cache_key = None

    def visit_func_expr(self, node: FunctionExpression) -> Value:
        if (expr := super().visit_func_expr(node)) is not NotImplemented:
            return expr

        assert isinstance(node.callee, IdentifierExpression)

        symbol = self.symbols.get(node.callee.name)

        if not symbol:
            return UnreachableValue()

        assert isinstance(symbol, FunctionValue)

        if isinstance(symbol.func, FunctionDefStatement):
            func = symbol.func

            with self.new_scope():
                args = [arg.accept(self) for arg in node.args]

                for name, arg in zip(func.arg_names, args, strict=True):
                    self.symbols[name] = arg

                return func.body.accept(self)

        if callable(symbol.func):
            # TODO: make this type-safe
            return symbol.func(self, node)

        return UnreachableValue()

    def visit_cache_stmt(self, node: CacheStatement) -> Value:
        print(  # noqa: T201
            "Caching is not yet supported for locally ran workflows"
        )

        return UnitValue()


def run_pipeline(
    contents: str,
    filename: str | None = None,
    trigger: Trigger | None = None,
) -> None:
    try:
        trigger = trigger or trigger_from_env()

        tree = parse_and_analyze(contents, trigger)

        tree.accept(EvalVisitor(trigger))

    except IgnoreWorkflow:
        pass

    except AstError as ex:  # pragma: no cover
        ex.filename = filename

        print(ex)  # noqa: T201


def main(filenames: list[str]) -> None:  # pragma: no cover
    files = [Path(x) for x in filenames]

    for file in files or find_ci_files(Path.cwd()):
        run_pipeline(file.read_text(), filename=str(file))


if __name__ == "__main__":
    main(sys.argv[1:])  # pragma: no cover
