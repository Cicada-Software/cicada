from hashlib import sha256
from pathlib import Path
from typing import cast

from cicada.ast.nodes import (
    FunctionExpression,
    NodeVisitor,
    StringValue,
    Value,
)
from cicada.eval.constexpr_visitor import CommandFailed


def hashOf(  # noqa: N802
    visitor: NodeVisitor[Value], node: FunctionExpression
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
