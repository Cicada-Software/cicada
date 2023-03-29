# The `let` Statement

The `let` statement allows for defining variables. A simple example of a variable
declaration would be:

```
let name = "bob"
```

Here we define a variable named `name` and assign it the string `bob`. By default,
all variables are immutable (ie, cannot be modified). There is currently no support
for mutable variables (though it is planned). The type of `name` is autodeduced as
type `string` because `"bob"` is a string.

Variables in the Cicada DSL are block-scoped, meaning they are only available in the
block they define. Variables can also be shadowed, meaning they can be redefined without
any errors:

```
let num = 1
let num = num * 2
```

In this contrived example, we first assign the value `1` to `num`, then create a new
variable (also called `num`) and assign it the value `2`. Whenever `num` is referenced
now, the most recently assigned `num`, in this case, the second one, will be used.
