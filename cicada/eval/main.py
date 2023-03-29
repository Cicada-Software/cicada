import shlex
import subprocess
import sys
from pathlib import Path

from cicada.api.settings import trigger_from_env
from cicada.ast.entry import parse_and_analyze
from cicada.ast.generate import AstError
from cicada.ast.nodes import (
    BooleanValue,
    FunctionExpression,
    NumericValue,
    RecordValue,
    StringValue,
    Value,
)
from cicada.ast.semantic_analysis import IgnoreWorkflow
from cicada.ast.types import RecordType
from cicada.eval.constexpr_visitor import ConstexprEvalVisitor
from cicada.eval.find_files import find_ci_files


def to_string(value: Value) -> str:
    match value:
        case StringValue() | NumericValue():
            return str(value.value)

        case BooleanValue():
            return "true" if value.value else "false"

    assert False, "impossible"


class EvalVisitor(ConstexprEvalVisitor):
    def visit_func_expr(self, node: FunctionExpression) -> Value:
        if node.name == "shell":
            args: list[str] = []

            for arg in node.args:
                args.append(to_string(arg.accept(self)))

            # TODO: test this
            args = [shlex.quote(arg) for arg in args]

            process = subprocess.run(["/bin/sh", "-c", " ".join(args)])

            if process.returncode != 0:
                sys.exit(process.returncode)

        # TODO: return rich "command type" value
        return RecordValue({}, RecordType())


def run_pipeline(contents: str, filename: str | None = None) -> None:
    try:
        trigger = trigger_from_env()

        tree = parse_and_analyze(contents, trigger)

        tree.accept(EvalVisitor(trigger))

    except IgnoreWorkflow:
        # TODO: test this
        pass

    except AstError as ex:  # pragma: no cover
        ex.filename = filename

        print(ex)


def main(filenames: list[str]) -> None:  # pragma: no cover
    files = [Path(x) for x in filenames]

    for file in files or find_ci_files(Path.cwd()):
        run_pipeline(file.read_text(), filename=str(file))


if __name__ == "__main__":
    main(sys.argv[1:])  # pragma: no cover
