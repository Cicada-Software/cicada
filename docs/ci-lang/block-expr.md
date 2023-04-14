# The Block Expression

The block expression is sort of an "invisible" expression, meaning you don't explicitly
create them: They are implicitly created whenever you have an indented block. Blocks are
essentially a list of expressions that get evaluated one after another, and the last
expression of the block is the return value of the block expression.

For example:

```
let x =
  let y = 123
  y

echo (x)
```

Here we are creating an indented block, assigning `123` to `y`, then evaluating (ie, returning) `y`
from that block, which finally gets assigned to `x`.
