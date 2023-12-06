# The `for` Statement

The for statement allows you to repeat a block of code with with a given value:

```
for name in ["alice", "bob"]:
  echo hello, (name)!
```

Currently you can only use `list` types. Using non-list types is an error:

```
for x in 1:  # error: expected list type
  echo x
```

For statements are technically expressions, though they only return the unit type (`()`).
This may change in the future.
