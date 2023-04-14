# The `if` Expression

The `if` expression can be used to conditionally run code. Like most programming languages,
an `if` expression has a condition and a body:

```
let condition = true

if condition:
  echo this is the body
```

In this example, `condition` is truthy, so the body of the `if` expression runs the `echo` command.
`condition` can be any truthy/falsey type including `bool`, `string`, and `number`.

> Currently `elif` and `else` blocks are not supported. This will be added in the near future.

Like the name implies, `if` expressions are expressions, and can be used in conjunction with
other expressions:

```
let x =
  if true:
    123
```

The result of an `if` expression is the last expression in the body, in this case, `123`.
The body of an `if` expression is a special type of expression called a "block",
which you can read more about [here](./block-expr.md).
