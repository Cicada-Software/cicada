from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from cicada.ast.entry import parse_and_analyze
from cicada.ast.nodes import BooleanValue, NumericValue, StringValue, UnitValue
from cicada.eval.main import EvalVisitor, run_pipeline


@contextmanager
def mock_exec(*, returncode: int = 0) -> Iterator[Mock]:
    m = MagicMock()

    m.stdout.read = AsyncMock(return_value="")
    m.wait = AsyncMock()
    m.returncode = returncode

    with patch("asyncio.subprocess.create_subprocess_exec", return_value=m) as p:
        yield p


async def test_calling_shell_function_invokes_sh_binary() -> None:
    with mock_exec() as p:
        await run_pipeline("shell echo hello")

    assert p.call_args.args == ("/bin/sh", "-c", "echo hello")


async def test_failing_shell_command_calls_exit() -> None:
    with (
        mock_exec(returncode=1),
        patch("sys.exit") as sys_exit,
    ):
        await run_pipeline("shell some_failing_command")

    assert sys_exit.call_args == call(1)


async def test_calling_shell_function_with_exprs() -> None:
    with mock_exec() as p:
        await run_pipeline('let x = 123\nshell echo (x) (456) ("789") (true)')

    assert p.call_args.args == ("/bin/sh", "-c", "echo 123 456 789 true")


async def test_calling_shell_function_escapes_shell_code() -> None:
    with mock_exec() as p:
        await run_pipeline('shell echo ("$ABC") (";") ("echo hi")')

    assert p.call_args.args == ("/bin/sh", "-c", "echo '$ABC' ';' 'echo hi'")


async def test_can_call_multiple_functions() -> None:
    """
    Fixes bug where the eval visitor exited after running the first function.

    This test could be simplified by creating a variable after the functions
    execute, then check if it exists in the context, but this will suffice.
    """

    with mock_exec() as p:
        await run_pipeline("echo hello\necho world")

    assert [call.args for call in p.call_args_list] == [
        ("/bin/sh", "-c", "echo hello"),
        ("/bin/sh", "-c", "echo world"),
    ]


async def test_calling_builtin_print_function_calls_print() -> None:
    with patch("builtins.print") as p:
        await run_pipeline('print("testing 123")')

    assert p.call_args == call("testing 123")


async def test_eval_user_defined_func() -> None:
    code = """
let mut ran = false

fn f():
  ran = true

f()
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    ran = visitor.symbols.get("ran")

    assert ran
    assert isinstance(ran, BooleanValue)
    assert ran.value


async def test_function_is_only_ran_if_called() -> None:
    code = """
let mut ran = false

fn f():
  ran = true
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    ran = visitor.symbols.get("ran")

    assert ran
    assert isinstance(ran, BooleanValue)
    assert not ran.value


async def test_function_creates_its_own_scope() -> None:
    code = """
fn f():
  let x = true

f()
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    assert not visitor.symbols.get("x")


async def test_function_passes_arguments() -> None:
    code = """
let mut str = ""

fn concat(x, y):
  # TODO: fix = having higher precedence
  str = (x + y)

concat("hello", " world")
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    symbol = visitor.symbols.get("str")

    assert symbol
    assert isinstance(symbol, StringValue)
    assert symbol.value == "hello world"


async def test_function_returns_return_value() -> None:
    code = """
fn add(x: number, y: number) -> number:
    x + y

let num = add(1, 2)
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    symbol = visitor.symbols.get("num")

    assert symbol
    assert isinstance(symbol, NumericValue)
    assert symbol.value == 3


async def test_function_with_unit_type_rtype_returns_return_unit_value() -> None:
    code = """
fn f():
    echo hi

let x = f()
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    symbol = visitor.symbols.get("x")

    assert symbol
    assert isinstance(symbol, UnitValue)


async def test_strip_string_function() -> None:
    code = """
let input = " hello world "
let x = input.strip()
"""

    tree = await parse_and_analyze(code)

    visitor = EvalVisitor()
    await tree.accept(visitor)

    symbol = visitor.symbols.get("x")

    assert symbol
    assert isinstance(symbol, StringValue)
    assert symbol.value == "hello world"
