from cicada.ast.entry import parse_and_analyze
from cicada.ast.nodes import BooleanValue
from cicada.eval.main import EvalVisitor


def test_eval_starts_with() -> None:
    code = """
let x = "hello world"
let t = x.starts_with("hello")
let f = x.starts_with("xyz")
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    t = visitor.symbols.get("t")
    f = visitor.symbols.get("f")

    assert t
    assert isinstance(t, BooleanValue)
    assert t.value

    assert f
    assert isinstance(f, BooleanValue)
    assert not f.value


def test_eval_ends_with() -> None:
    code = """
let x = "hello world"
let t = x.ends_with("world")
let f = x.ends_with("xyz")
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    t = visitor.symbols.get("t")
    f = visitor.symbols.get("f")

    assert t
    assert isinstance(t, BooleanValue)
    assert t.value

    assert f
    assert isinstance(f, BooleanValue)
    assert not f.value
