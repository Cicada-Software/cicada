# The `let` Expression

The `let` expression allows for defining variables. A simple example of a variable
declaration would be:

```
let name = "bob"
```

Here we define a variable named `name` and assign it the string `bob`. By default,
all variables are immutable (ie, cannot be modified). The type of `name` is autodeduced as
type `string` because `"bob"` is a string.

Variables in the Cicada DSL are block-scoped, meaning they are only available in the
block they define. Variables can also be shadowed, meaning they can be redefined without
any errors:

```
let num = 1
let num = num * 2
```

In this contrived example above we first assign the value `1` to `num`, then create a new
variable (also called `num`) and assign it the value `2`. Whenever `num` is referenced
now, the most recently assigned `num`, in this case, the second one, will be used.

## Scoping

While `let` can be used as a statement (that is, on it's own line), it can also be used
in other expressions such as the `if` expression:

```
if let number = 123:
  echo your number is (number)

# Error, number is not defined here.
echo (number)
```

In the above example, `number` is created using a `let` expression. Since `123` is truthy,
the `if` condition passes, and the first `echo` command would be ran. The second `echo`
command causes an error though, since `number` is only scoped to the body of the `if` expression.

## Mutable Variables

You can use the `mut` keyword to make a variable mutable:

```
let mut num = 123
```

While there currently is no way to reassign `num`, when there is you will be allowed to!
