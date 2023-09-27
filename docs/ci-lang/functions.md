# Functions

Functions are user-defined bits of code that can be called directly in your workflows.
Like normal programming languages, functions can have arguments, return values, and so forth.

Here is how you define functions in Cicada:

```
fn greet(name):
  echo Hello (name)!

greet("Bob")
```

When ran, this workflow will output the following:

```
Hello Bob!
```

Functions can optionally be typed. Here is the last function with explicit types added:

```
fn greet(name: string) -> ():
  echo Hello (name)!
```

When function arguments aren't typed they default to `string` types, and when no return type is
specified, the unit type `()` is assumed.

Since there are no explicit `return` statements yet, values at the end of a function block are implicitly
returned. See the docs on [The Block Expression](./block-expr.md) for more info.

> When the unit type `()` is used as a return type, no warnings or errors are emitted if you try to return
> non-unit type (such as `number`). This means you don't need to worry about explicitly returning `()` everywhere.
