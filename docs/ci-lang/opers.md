# Operators

This is a list of operators currently supported in Cicada:

| Operator              | Supported Types    | Result Type  | Example                    |
|-----------------------|--------------------|--------------|----------------------------|
| `+`                   | `number`, `string` | *lhs type*   | `1 + 2` → `3`              |
| `-` (subtract)        | `number`           | `number`     | `1 - 2` → `-1`             |
| `*`                   | `number`           | `number`     | `2 * 3` → `6`              |
| `/`                   | `number`           | `number`     | `10 / 2` → `5`             |
| `mod` (modulus)       | `number`           | `number`     | `10 mod 3` → `1`           |
| `^` (power)           | `number`           | `number`     | `2 ^ 3` → `8`              |
| `and`                 | `number`, `bool`   | *lhs type*   | `true and false` → `false` |
| `or`                  | `number`, `bool`   | *lhs type*   | `true or false` → `true`   |
| `xor`                 | `number`, `bool`   | *lhs type*   | `true xor false` → `true`  |
| `is` (equality)       | *any*              | `bool`       | `1 is 2` → `false`         |
| `is not` (inequality) | *any*              | `bool`       | `1 is not 2` → `true`      |
| `<`                   | `number`           | `bool`       | `1 < 2` → `true`           |
| `<=`                  | `number`           | `bool`       | `1 <= 2` → `true`          |
| `>`                   | `number`           | `bool`       | `1 > 2` → `false`          |
| `>=`                  | `number`           | `bool`       | `1 >= 2` → `false`         |
| `in`                  | `string`           | `bool`       | `"x" in "y"` → `false`     |
| `not in`              | `string`           | `bool`       | `"x" not in "y"` → `true`  |
| `not`                 | `bool`             | `bool`       | `not true` → `false`       |
| `-` (negate)          | `number`           | `number`     | `-(1 - 2)` → `1`           |
| `=` (reassign)        | *any*              | *any*        | `x = 1` → `1`              |

For all the above operators, the left and right hand side type must be the same. For example,
the following is not allowed:

```
let x = 1 + "2"
```

The `=` (assign) operator is useful when you want to reassign a variable and use it in an
expression:

```
let mut x = 1

if x = f():
  # use x for something
```
