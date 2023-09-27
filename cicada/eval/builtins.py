import subprocess
import sys
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import cast

from cicada.ast.nodes import (
    FunctionExpression,
    NumericValue,
    RecordValue,
    StringValue,
    UnitValue,
)
from cicada.ast.types import CommandType
from cicada.eval.constexpr_visitor import (
    CommandFailed,
    ConstexprEvalVisitor,
    value_to_string,
)


# TODO: rename function
def hashOf(  # noqa: N802
    visitor: ConstexprEvalVisitor, node: FunctionExpression
) -> StringValue:
    files: list[Path] = []

    for arg in node.args:
        filename = cast(StringValue, arg.accept(visitor)).value

        if "*" in filename:
            globs = list(Path().glob(filename))

            if not globs:
                # TODO: add more info
                print("No files to hash after expanding glob")  # noqa: T201

                raise CommandFailed(1)

            files.extend(globs)

        else:
            files.append(Path(filename))

    hashes = sha256()

    for file in sorted(files):
        if not file.exists():
            print(f"File `{file}` does not exist")  # noqa: T201

            raise CommandFailed(1)

        hashes.update(file.read_bytes())

    return StringValue(hashes.hexdigest())


def builtin_print(
    visitor: ConstexprEvalVisitor, node: FunctionExpression
) -> UnitValue:
    args: list[str] = []

    for arg in node.args:
        value = value_to_string(arg.accept(visitor))

        assert isinstance(value, StringValue)

        args.append(value.value)

    print(*args)  # noqa: T201

    return UnitValue()


def builtin_shell(
    visitor: ConstexprEvalVisitor, node: FunctionExpression
) -> RecordValue:
    args: list[str] = []

    for arg in node.args:
        value = value_to_string(arg.accept(visitor))

        assert isinstance(value, StringValue)

        args.append(value.value)

    # `shlex.join` is intentionally not used here to allow for shell features
    # like piping and env vars.

    process = subprocess.run(  # noqa: PLW1510
        ["/bin/sh", "-c", " ".join(args)],  # noqa: S603
        env=visitor.trigger.env if visitor.trigger else None,
        capture_output=True,
    )

    if process.returncode != 0:
        sys.exit(process.returncode)

    # TODO: add function to handle this
    return RecordValue(
        {
            "exit_code": NumericValue(Decimal(process.returncode)),
            # TODO: what should happen if invalid unicode sequence is found?
            "stdout": StringValue(process.stdout.decode()),
            "stderr": StringValue(process.stdout.decode()),
        },
        CommandType(),
    )
