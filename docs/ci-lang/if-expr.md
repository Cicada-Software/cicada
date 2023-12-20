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

Like the name implies, `if` expressions are expressions, and can be used in conjunction with
other expressions:

```
let x =
  if true:
    123
  else:
    456
```

The result of an `if` expression is the last expression in the body, in this case, `123`.
The body of an `if` expression is a special type of expression called a "block",
which you can read more about [here](./block-expr.md).

## `elif`

Use `elif` to add more conditions in case your first `if` condition isn't hit:

```
if x:
  echo x is truthy

elif y:
  echo y is truthy
```

## `else`

Use `else` to execute code if no `if`/`elif` is hit:

```
if x:
  echo x was truthy

else:
  echo x was falsey
```

## Scoping

Each `if`, `elif`, and `else` block creates its own scope. This means that variables declared
inside of those blocks cannot be used after the block has finished:

```
if x:
  let y = 123
else:
  let y = 456

print(y)  # error, y is not defined
```

To fix this, assign the result of the `if` expression to `y` instead:

```
let y =
  if x:
    123
  else:
    456
```

Or you can make `y` mutable and reassign it:

```
let mut y = 0

if x:
  y = 123
else:
  y = 456
```

With these scoping rules you can create new variables scoped to a single `if`/`elif` expression:

```
let name = " bob "

if let stripped_name = name.strip():
  echo Hello, (stripped_name)!

# stripped_name cannot be used here anymore
```

The above code will print `Hello, bob!`.
