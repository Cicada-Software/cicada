import shlex
import subprocess
import sys
from pathlib import Path

from cicada.api.settings import trigger_from_env
from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import AstError
from cicada.ast.nodes import (
    FunctionExpression,
    RecordValue,
    StringValue,
    UnitValue,
    Value,
)
from cicada.ast.semantic_analysis import IgnoreWorkflow
from cicada.ast.types import RecordType
from cicada.domain.triggers import Trigger
from cicada.eval.constexpr_visitor import ConstexprEvalVisitor, value_to_string
from cicada.eval.find_files import find_ci_files


class EvalVisitor(ConstexprEvalVisitor):
    def visit_func_expr(self, node: FunctionExpression) -> Value:
        args: list[str] = []

        for arg in node.args:
            value = value_to_string(arg.accept(self))

            assert isinstance(value, StringValue)

            args.append(value.value)

        if node.name == "shell":
            process = subprocess.run(
                ["/bin/sh", "-c", shlex.join(args)],  # noqa: S603
                env=self.trigger.env if self.trigger else None,
            )

            if process.returncode != 0:
                sys.exit(process.returncode)

            # TODO: return rich "command type" value
            return RecordValue({}, RecordType())

        if node.name == "print":
            print(*args)  # noqa: T201

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
