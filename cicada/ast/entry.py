from cicada.ast.generate import generate_ast_tree
from cicada.ast.nodes import FileNode
from cicada.ast.semantic_analysis import SemanticAnalysisVisitor
from cicada.domain.triggers import Trigger
from cicada.parse.tokenize import tokenize


def parse_and_analyze(
    code: str,
    trigger: Trigger | None = None,
    *,
    validate: bool = True,
) -> FileNode:
    tokens = tokenize(code)
    tree = generate_ast_tree(tokens)

    if validate:
        tree.accept(SemanticAnalysisVisitor(trigger))

    return tree
