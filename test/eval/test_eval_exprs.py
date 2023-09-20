from decimal import Decimal

from cicada.ast.common import json_to_record
from cicada.ast.entry import parse_and_analyze
from cicada.ast.nodes import (
    BooleanValue,
    NumericValue,
    RecordValue,
    StringValue,
)
from cicada.eval.main import EvalVisitor
from test.eval.test_eval_statements import make_dummy_commit_trigger


def test_unary_not_expr() -> None:
    tree = parse_and_analyze("let x = not true")

    visitor = EvalVisitor()
    tree.accept(visitor)

    expr = visitor.symbols["x"]

    assert isinstance(expr, BooleanValue)
    assert expr.value is False


def test_unary_negate_expr() -> None:
    tree = parse_and_analyze("let x = - 123")

    visitor = EvalVisitor()
    tree.accept(visitor)

    expr = visitor.symbols["x"]

    assert isinstance(expr, NumericValue)
    assert expr.value == -123


def test_member_expr() -> None:
    # Disabling validation for now since there is no way to create record types
    # from within the language, for now they have to be inserted in at runtime.
    tree = parse_and_analyze("let x = a.b", validate=False)

    visitor = EvalVisitor()

    a = json_to_record({"b": 123})
    visitor.symbols["a"] = a

    tree.accept(visitor)

    expr = visitor.symbols["x"]
    assert isinstance(expr, NumericValue)
    assert expr.value == 123


def test_numeric_binary_exprs() -> None:
    tree = parse_and_analyze(
        """\
let pow = 2 ^ 8
let add = 1 + 2
let sub = 2 - 1
let mult = 2 * 5
let div = 9 / 3
let _mod = 10 mod 3

let _and = 0b1100 and 0b0011
let _or = 0b1100 or 0b0011
let _xor = 0b1100 xor 0b0011

# order of operation checks
let a = 1 + 2 * 3
let b = 1 * 2 + 3
"""
    )

    visitor = EvalVisitor()
    tree.accept(visitor)

    expected = {
        "pow": 2**8,
        "add": 1 + 2,
        "sub": 2 - 1,
        "mult": 2 * 5,
        "div": 9 / 3,
        "_mod": 10 % 3,
        "_and": 0b1100 & 0b0011,
        "_or": 0b1100 | 0b0011,
        "_xor": 0b1100 ^ 0b0011,
        # order of operation checks
        "a": 1 + 2 * 3,
        "b": 1 * 2 + 3,
    }

    for name, value in expected.items():
        symbol = visitor.symbols[name]

        assert isinstance(symbol, NumericValue)
        assert symbol.value == value, f"Variable `{name}` does not match"


def test_boolean_binary_exprs() -> None:
    tree = parse_and_analyze(
        """\
let _and = true and false
let _or = true or false
let _xor = true xor false
let less_than = 3 < 10
let gtr_than = 3 > 10
let less_than_eq = 3 <= 10
let gtr_than_eq = 3 >= 10
let _is = 123 is 123
let _in = "a" in "abc"
let not_in = "a" not in "abc"
"""
    )

    visitor = EvalVisitor()
    tree.accept(visitor)

    expected = {
        "_and": False,
        "_or": True,
        "_xor": True,
        "less_than": True,
        "gtr_than": False,
        "less_than_eq": True,
        "gtr_than_eq": False,
        "_is": True,
        "_in": "a" in "abc",
        "not_in": "a" not in "abc",
    }

    for name, value in expected.items():
        symbol = visitor.symbols[name]

        assert isinstance(symbol, BooleanValue)
        assert symbol.value == value, f"Variable `{name}` does not match"


def test_string_add_binary_expr() -> None:
    tree = parse_and_analyze('let x = "hello " + "world"')

    visitor = EvalVisitor()
    tree.accept(visitor)

    symbol = visitor.symbols["x"]

    assert isinstance(symbol, StringValue)
    assert symbol.value == "hello world"


def test_use_env_var_exprs() -> None:
    trigger = make_dummy_commit_trigger()
    trigger.env = {"TESTING": "123"}

    tree = parse_and_analyze("let x = env.TESTING", trigger)

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

    symbol = visitor.symbols["x"]

    assert isinstance(symbol, StringValue)
    assert symbol.value == "123"


def test_eval_if_condition_truthiness() -> None:
    code = """\
let mut a = false
let mut b = false
let mut c = false
let mut d = false
let mut e = false
let mut f = false

if 1:
    a = true
if true:
    b = true
if "abc":
    c = true

if 0:
    d = true
if false:
    e = true
if "":
    f = true
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    for symbol in ("a", "b", "c", "d", "e", "f"):
        expr = visitor.symbols[symbol]

        assert isinstance(expr, BooleanValue)

        expect_true = symbol in ("a", "b", "c")

        assert expr.value == expect_true


def test_let_expr_scoping_semantics() -> None:
    code = """\
let a = 1

let mut b = 1
if true:
    b = 2

let c = 1
if true:
    let mut c = 2
    c = 3

let mut d = 1
if true:
    d = 2
d = 3
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    values = {
        "a": 1,
        "b": 2,
        "c": 1,
        "d": 3,
    }

    for symbol, value in values.items():
        expr = visitor.symbols[symbol]

        assert isinstance(expr, NumericValue)

        assert expr.value == value


def test_eval_falsey_if_expr() -> None:
    code = """\
if false:
    let x = 1
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    assert "x" not in visitor.symbols


def test_eval_float_exprs() -> None:
    tree = parse_and_analyze("let x = 0.1 + 0.2")

    visitor = EvalVisitor()
    tree.accept(visitor)

    x = visitor.symbols["x"]

    assert isinstance(x, NumericValue)
    assert x.value == Decimal("0.3")


def test_update_existing_env_var() -> None:
    trigger = make_dummy_commit_trigger()
    trigger.env = {"TESTING": "abc"}

    tree = parse_and_analyze('env.TESTING = "xyz"', trigger)

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

    symbol = visitor.symbols["env"]

    assert isinstance(symbol, RecordValue)
    assert symbol.value["TESTING"] == StringValue("xyz")


def test_set_new_env_var() -> None:
    trigger = make_dummy_commit_trigger()
    trigger.env = {}

    tree = parse_and_analyze('env.TESTING = "xyz"', trigger)

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

    symbol = visitor.symbols["env"]

    assert isinstance(symbol, RecordValue)
    assert symbol.value["TESTING"] == StringValue("xyz")


def test_get_secret() -> None:
    trigger = make_dummy_commit_trigger()
    trigger.secret = {"API_KEY": "abc123"}

    tree = parse_and_analyze("let x = secret.API_KEY", trigger)

    visitor = EvalVisitor(trigger)
    tree.accept(visitor)

    symbol = visitor.symbols["secret"]

    assert isinstance(symbol, RecordValue)
    assert symbol.value["API_KEY"] == StringValue("abc123")

    symbol = visitor.symbols["x"]

    assert isinstance(symbol, StringValue)
    assert symbol.value == "abc123"
