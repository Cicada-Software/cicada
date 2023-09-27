# The `shell` Statement

The `shell` statement is the main way to run commands in Cicada. The `shell` statement allows you
to run commands and as well as execute inline shell code in your workflow.

> Arguments passed to `shell` are passed directly to `/bin/sh`. This means you get all the features,
> quirks, and potential security considerations involved with using shell code in your workflows.
> Please read the [Security Considerations](#security-considerations) for information on how to better
> secure your workflows.

## Examples

Here are a few examples of how the `shell` statement can be used in workflows:

### Run a Command

```
shell npm install
```

This will run `npm install` in the current directory.

### Pass Expressions as Arguments

```
let name = "Bob"

shell echo You name is (name)
```

Cicada will pass `name` as the argument for `(name)`. The `()` notation is used to
differentiate from the typical `$` notation used in shell.

Note you can use any valid Cicada expression as an argument, not just variable names:

```
shell echo 1 + 2 = (1 + 2)
```

The above workflow will print out `1 + 2 = 3`.

### Capture stdout/stderr

In Cicada you can capture and manipulate the stdout of a command by assigning it to
a variable and accessing it's properties:

```
let cmd =
  shell echo Hello world!

print(cmd.stdout)
```

Running this workflow will print `Hello world!` \*. Using stdout like this helps you
utilize more of what Cicada has to offer, without having to rely on shell scripts.

> \* An extra newline will be printed since `echo` and `print` both add newlines.

### Using Shell Features

You can also use `shell` to gain access to shell features like env vars, piping, and conditional
execution:

```
# Print the current directory
shell echo Current dir: $PWD

# Get the top 10 biggest files/folders in the "src" folder
shell du src | sort -nr | head -n 10

# Print message and exit if backup fails
shell ./backup.sh || { echo "Backup failed" && exit 1; }
```

While shell code can be very useful in writing your workflows, we encourage you to use the Cicada DSL
instead of shell scripts wherever possible.

### Run Shell Scripts

In addition to running single line shell commands, the `shell` statement can be used to
run larger, multi-line shell scripts:

```
shell "
  echo running tests
  ./run-tests.sh

  if [ "$?" = "1" ]; then
    echo tests failed
  else
    echo tests passeed
  fi
"
```

This shell script runs `./run-tests.sh` and print whether the tests passed or failed
based on the resulting exit code.

## Shell Aliases

Shell aliases are special identifiers that can be used directly without the need to prefix it with `shell`.

For example, the following are equivalent in Cicada:

```
shell echo hi

echo hi
```

These are the current commands that are allowed to be used as aliases, though this list may grow in the future:

* `cd`
* `cp`
* `echo`
* `git`
* `ls`
* `make`
* `mkdir`
* `rm`

## Notes on Environment Variables

By default, Cicada will inject environment variables into each command before running it.
In addition, environment variables that are set while running a `shell` command will not
be saved.

For example:

```
shell echo ----
shell env

env.HELLO = "world"

shell echo ----
shell env

shell echo ----
shell export TESTING="123"
shell env
```

This will emit something similar to the following:

```
PWD=<CURRENT DIRECTORY>
SHLVL=0
_=/usr/bin/env
----
HELLO=world
PWD=<CURRENT DIRECTORY>
SHLVL=0
_=/usr/bin/env
----
HELLO=world
PWD=<CURRENT DIRECTORY>
SHLVL=0
_=/usr/bin/env
```

Notice that the `HELLO` env var is passed to the next commands, but `TESTING`
is not.

## Security Considerations

Since the `shell` statement allows you to run arbitrary commands, it is
paramount that you ensure it is safeguarded from malicious users.

Because `shell` will forward commands to `/bin/sh`, any arguments passed
to it must be trusted and secured. The following is an example of a malicious
command being passed using a variable:

```
let name = "hacker; echo Command injection"

shell echo Your name is: (name)
```

Running the above workflow results in the following:

```
Your name is: hacker
Command injection
```

Ensure that you only pass *trusted input* to commands. Example sources of untrusted
input are commit author usernames and branch names.
