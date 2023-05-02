from cicada.ast.generate import generate_ast_tree
from cicada.ast.nodes import LineInfo, StringExpression
from cicada.ast.types import StringType
from cicada.parse.tokenize import tokenize


def test_create_string_expr_from_string_literal() -> None:
    token = list(tokenize('"hello world"'))[0]

    node = StringExpression.from_token(token)

    assert node == StringExpression(
        info=LineInfo(1, 1, 1, 13),
        value="hello world",
        type=StringType(),
    )


def test_create_string_expr_with_escapes() -> None:
    token = list(tokenize(r'"\x41\u0042C"'))[0]

    node = StringExpression.from_token(token)

    assert node == StringExpression(
        info=LineInfo(1, 1, 1, 13),
        value="ABC",
        type=StringType(),
    )


def test_create_string_expr_from_identifier() -> None:
    token = list(tokenize("hello"))[0]

    node = StringExpression.from_token(token)

    assert node == StringExpression(
        info=LineInfo(1, 1, 1, 5),
        value="hello",
        type=StringType(),
    )


def test_stringify_nodes() -> None:
    code = """\
on git.push

echo hello world

let x = 1337

let y = x

let z = (y)

let a = x.y
let b = true
let c = not true
let e = 1 + 2

if true:
  let x = 123

let mut f = 0
"""

    tree = generate_ast_tree(tokenize(code))

    expected = """\
FileNode:
  OnStatement('git.push') # 1:1..1:2
  FunctionExpression(shell=True): # 3:1..3:4
    0=StringExpression('echo') # 3:1..3:4
    1=StringExpression('hello') # 3:6..3:10
    2=StringExpression('world') # 3:12..3:16
  LetExpression(): # 5:1..5:3
    name=x
    expr=NumericExpression(1337) # 5:9..5:12
  LetExpression(): # 7:1..7:3
    name=y
    expr=IdentifierExpression('x') # 7:9..7:9
  LetExpression(): # 9:1..9:3
    name=z
    expr=ParenthesisExpression: # 9:9..9:9
      IdentifierExpression('y') # 9:10..9:10
  LetExpression(): # 11:1..11:3
    name=a
    expr=MemberExpression(): # 11:9..11:11
      lhs=IdentifierExpression('x') # 11:9..11:9
      name=y
  LetExpression(): # 12:1..12:3
    name=b
    expr=BooleanExpression(True) # 12:9..12:12
  LetExpression(): # 13:1..13:3
    name=c
    expr=UnaryExpression(UnaryOperator.NOT): # 13:9..13:11
      BooleanExpression(True) # 13:13..13:16
  LetExpression(): # 14:1..14:3
    name=e
    expr=BinaryExpression(BinaryOperator.ADD): # 14:9..14:9
      NumericExpression(1) # 14:9..14:9
      NumericExpression(2) # 14:13..14:13
  IfExpression: # 16:1..16:2
    cond=BooleanExpression(True) # 16:4..16:7
    body=BlockExpression: # 17:3..17:3
      0=LetExpression(): # 17:3..17:5
        name=x
        expr=NumericExpression(123) # 17:11..17:13
  LetExpression(mutable): # 19:1..19:3
    name=f
    expr=NumericExpression(0) # 19:13..19:13"""

    assert str(tree) == expected
