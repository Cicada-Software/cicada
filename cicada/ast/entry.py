from pathlib import Path

from cicada.ast.generate import generate_ast_tree
from cicada.ast.nodes import FileNode
from cicada.ast.semantic_analysis import SemanticAnalysisVisitor
from cicada.domain.triggers import Trigger
from cicada.parse.tokenize import tokenize


async def parse_and_analyze(
    code: str,
    trigger: Trigger | None = None,
    *,
    validate: bool = True,
    file_root: Path | None = None,
) -> FileNode:
    tokens = tokenize(code)
    tree = generate_ast_tree(tokens)

    if validate:
        await tree.accept(SemanticAnalysisVisitor(trigger, file_root=file_root))

    return tree
