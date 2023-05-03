from cicada.ast.nodes import (
    BooleanValue,
    FunctionExpression,
    OnStatement,
    Value,
)
from cicada.eval.constexpr_visitor import ConstexprEvalVisitor


class ShouldRunWorkflow(Exception):
    should_run: bool

    def __init__(self, /, should_run: bool) -> None:
        self.should_run = should_run


class OnStatementEvalVisitor(ConstexprEvalVisitor):
    """
    This is a custom visitor very similar to the constexpr visitor, except that
    it only runs long enough to detect whether the event trigger will trigger
    the workflow's `on` statement. To prevent parsing more than needed, an
    exception is thrown which includes a boolean value indicating whether the
    workflow should run or not.
    """

    def visit_on_stmt(self, node: OnStatement) -> Value:
        if node.where:
            result = node.where.accept(self)

            if isinstance(result, BooleanValue):
                raise ShouldRunWorkflow(result.value)

            raise ShouldRunWorkflow(False)

        raise ShouldRunWorkflow(True)

    def visit_func_expr(self, _: FunctionExpression) -> Value:
        raise ShouldRunWorkflow(False)
