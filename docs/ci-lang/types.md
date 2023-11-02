# Types and Literals

This is an overview of the different types available in Cicada, and how you can create them.

## The Unknown Type

If you encounter this type, you usually have a bug in your code (or there is a bug in Cicada). This type is
used when Cicada can't deduce what type you are trying to use, meaning you may need to include a type hint
to tell Cicada what type it should be expecting (more on that later).

## The Unit Type

The unit type, written as `()`, is the "nothing" type, similar to `None` in Python or `void` in C.
This type is useful when declaring a function doesn't return anything.

## The `bool` Type

The `bool` type can only have 2 values: `true` or `false`.

## The `number` Type

In Cicada, numbers are represented using a single `number` type, meaning there is no distinction between `int`s
and `float`s.

There are many ways to create an `number` in Cicada since Cicada uses the same number semantics as Python:

```
# basic positive/negative numbers
let num = 123
let neg = -123

# floating point numbers
let pi = 3.1415

# number separators are supported too
let big_number = 123_456_789

# binary, octal, and hexadecimal numbers
let bin = 0b11001100
let oct = 0o777
let hex = 0xABCDEF
```

`number`s can be truthy. This means that in an `if` statement, non-zero numbers are considered `true`, and zero
is considered `false`:

```
let x = 1

if x:
  print("x is truthy")
```

> Note: Under the hood Cicada uses the `Decimal` type to represent numbers. This means you can represent
> numeric literals with exact prescision and do most math operations with zero loss of accuracy. Since
> Cicada is not meant to be used for fast math operations, the overhead of using a `Decimal` should not
> matter too much.

## The `string` Type

`string`s are similar to strings in other languages, like Python:

```
let x = "Hello world!"
```

You can create multi-line strings by adding newlines between your string:

```
let text = "
This is a block of text.
This text will be on a new line.
"
```

## The `list` Type

`list`s are still in the early stages, but you can use them to create a list of the same types.

Here is how you create a list in Cicada:

```
let nums = [1, 2, 3]
```

In this example, `x` is a `list` of `number`s. The explicit type for lists are written as `[T]`,
so in this example, `x` is of type `[number]`.
