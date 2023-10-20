# List Expressions

Lists allow you to store a collection of the same type. You can define a list like so:

```
let names = ["bob", "alice"]

let primes = [1, 2, 3, 5, 7, 11]
```

In the above example, `names` has a type of `[string]`, and `primes` has a type of `[number]`.
In Cicada, list types are written as `[T]` to indicate it's a list containing elements of type `T`.

When reassigning a list variable, the list type must be compatible:

```
let mut nums = [1, 2, 3]

# Error: Expression of type `[string]` cannot be assigned to type `[number]`
nums = ["a", "b", "c"]
```

## List Functions

Currently you can't do anything with lists once you define them, though more functionality
will be given to lists in the near future!
