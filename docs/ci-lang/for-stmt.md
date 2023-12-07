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

Like in other programming langauges, you can use `break` and `continue` to change the control flow
of your program. `break` will break out of the loop, and `continue` will skip the rest of the loop
and start the next iteration:

```
for num in [5, 4, 3, 2, 1, 0, -1]:
  if num is 0:
    break

  if num mod 2 is 1:
    continue

  echo (num) is even and non-zero
```
