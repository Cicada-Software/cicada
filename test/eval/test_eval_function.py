from unittest.mock import MagicMock, call, patch

from cicada.ast.entry import parse_and_analyze
from cicada.ast.nodes import BooleanValue, NumericValue, StringValue, UnitValue
from cicada.eval.main import EvalVisitor, run_pipeline


def test_calling_shell_function_invokes_sh_binary() -> None:
    m = MagicMock()

    # TODO: can this mocking be cleaned up?
    with (
        patch("subprocess.run", return_value=m) as p,
        patch.object(m, "returncode", 0),
    ):
        run_pipeline("shell echo hello")

    assert p.call_args == call(
        ["/bin/sh", "-c", "echo hello"],
        env=None,
        capture_output=True,
    )


def test_failing_shell_command_calls_exit() -> None:
    m = MagicMock()

    with (
        patch("subprocess.run", return_value=m),
        patch("sys.exit") as sys_exit,
        patch.object(m, "returncode", 1),
    ):
        run_pipeline("shell some_failing_command")

    assert sys_exit.call_args == call(1)


def test_calling_shell_function_with_exprs() -> None:
    m = MagicMock()

    with (
        patch("subprocess.run", return_value=m) as p,
        patch.object(m, "returncode", 0),
    ):
        run_pipeline('let x = 123\nshell echo (x) (456) ("789") (true)')

    assert p.call_args == call(
        ["/bin/sh", "-c", "echo 123 456 789 true"],
        env=None,
        capture_output=True,
    )


def test_can_call_multiple_functions() -> None:
    """
    Fixes bug where the eval visitor exited after running the first function.

    This test could be simplified by creating a variable after the functions
    execute, then check if it exists in the context, but this will suffice.
    """

    m = MagicMock()

    with (
        patch("subprocess.run", return_value=m) as p,
        patch.object(m, "returncode", 0),
    ):
        run_pipeline("echo hello\necho world")

    assert p.call_args_list == [
        call(["/bin/sh", "-c", "echo hello"], env=None, capture_output=True),
        call(["/bin/sh", "-c", "echo world"], env=None, capture_output=True),
    ]


def test_calling_builtin_print_function_calls_print() -> None:
    with patch("builtins.print") as p:
        run_pipeline('print("testing 123")')

    assert p.call_args == call("testing 123")


def test_eval_user_defined_func() -> None:
    code = """
let mut ran = false

fn f():
  ran = true

f()
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    ran = visitor.symbols.get("ran")

    assert ran
    assert isinstance(ran, BooleanValue)
    assert ran.value


def test_function_is_only_ran_if_called() -> None:
    code = """
let mut ran = false

fn f():
  ran = true
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    ran = visitor.symbols.get("ran")

    assert ran
    assert isinstance(ran, BooleanValue)
    assert not ran.value


def test_function_creates_its_own_scope() -> None:
    code = """
fn f():
  let x = true

f()
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    assert not visitor.symbols.get("x")


def test_function_passes_arguments() -> None:
    code = """
let mut str = ""

fn concat(x, y):
  # TODO: fix = having higher precedence
  str = (x + y)

concat("hello", " world")
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    symbol = visitor.symbols.get("str")

    assert symbol
    assert isinstance(symbol, StringValue)
    assert symbol.value == "hello world"


def test_function_returns_return_value() -> None:
    code = """
fn add(x: number, y: number) -> number:
    x + y

let num = add(1, 2)
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    symbol = visitor.symbols.get("num")

    assert symbol
    assert isinstance(symbol, NumericValue)
    assert symbol.value == 3


def test_function_with_unit_type_rtype_returns_return_unit_value() -> None:
    code = """
fn f():
    echo hi

let x = f()
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    symbol = visitor.symbols.get("x")

    assert symbol
    assert isinstance(symbol, UnitValue)


def test_strip_string_function() -> None:
    code = """
let input = " hello world "
let x = input.strip()
"""

    tree = parse_and_analyze(code)

    visitor = EvalVisitor()
    tree.accept(visitor)

    symbol = visitor.symbols.get("x")

    assert symbol
    assert isinstance(symbol, StringValue)
    assert symbol.value == "hello world"
