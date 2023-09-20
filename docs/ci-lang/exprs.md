# Expressions

This is a list of expressions supported in Cicada.

| Name                  | Supported Types    | Result Type  | Example                    |
|-----------------------|--------------------|--------------|----------------------------|
| Add                   | `number`, `string` | *lhs type*   | `1 + 2` → `3`              |
| Subtract              | `number`           | `number`     | `1 - 2` → `-1`             |
| Multiply              | `number`           | `number`     | `2 * 3` → `6`              |
| Divide                | `number`           | `number`     | `10 / 2` → `5`             |
| Modulus               | `number`           | `number`     | `10 mod 3` → `1`           |
| Power                 | `number`           | `number`     | `2 ^ 3` → `8`              |
| And                   | `number`, `bool`   | *lhs type*   | `true and false` → `false` |
| Or                    | `number`, `bool`   | *lhs type*   | `true or false` → `true`   |
| Xor                   | `number`, `bool`   | *lhs type*   | `true xor false` → `true`  |
| Is (equal)            | *any*              | `bool`       | `1 is 2` → `false`         |
| Is Not (equal)        | *any*              | `bool`       | `1 is not 2` → `true`      |
| Less Than             | `number`           | `bool`       | `1 < 2` → `true`           |
| Less Than or Equal    | `number`           | `bool`       | `1 <= 2` → `true`          |
| Greater Than          | `number`           | `bool`       | `1 > 2` → `false`          |
| Greater Than or Equal | `number`           | `bool`       | `1 >= 2` → `false`         |
| In                    | `string`           | `bool`       | `"x" in "y"` → `false`     |
| Not In                | `string`           | `bool`       | `"x" not in "y"` → `true`  |
| Not                   | *any*              | `bool`       | `not true` → `false`       |
| Negate                | `number`           | `number`     | `-(1 - 2)` → `1`           |
| Assign                | *any*              | *any*        | `x = 1` → `1`              |
