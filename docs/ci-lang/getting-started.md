# Your First Workflow

This is an introduction to the Cicada DSL (Domain-specific language). This DSL can be used for defining workflows,
which includes CI/CD (Continuous Integration/Continuous Deployment), automated testing/backups, and much more.
The Cicada DSL (which may be referred to as "The DSL" or just "Cicada") was designed from the ground up to meet
the growing needs of DevOps engineers, Full-stack engineers, or anyone else who spends a lot of time writing
and maintaining CI/CD workflows.

> Before you get started, make sure you've setup Cicada for your repository or organization. For info on how
> to set this up, see the [Getting Started docs](../getting-started.md).

To get started, create a file anywhere in your repository ending in `.ci`. One advantage of Cicada is that you
can structure your workflows however you want, and are not limited to a single `.yaml` file or `.github` folder
for all your workflows.

In your workflow file, add the following:

```
on git.push

echo Hello World!
```

This workflow file will run every time there is a `git push` to a repository. The `echo` command is a built-in
shell alias, meaning you can use it as if it where a built-in command. For less common commands, prefix it with
the `shell` command:

```
shell whoami
```

> Note that you cannot use the pipe operator (`|`) with the `shell` command, only one command can be executed at
> a time.

To make sure that your workflow works, try pushing to your repository. If you are using GitHub or Gitlab, you
should see a green check next to the commit indicating that the workflow completed successfully.

## Your Second Workflow

Now that you've created your first workflow, where can you go from here?

### Conditional Workflows

You can add a condition to the `on` statement to only run a workflow under certain conditions:

```
on git.push where event.branch is "main"

echo I am running on the main branch!
```

This workflow will run for every commit to a GitHub repository.

### Variables

Yes, you heard that right! Cicada is a full-fledged programming language, allowing you to define variables and
use them in commands:

```
let message = "hello world"

echo (message)
```

This workflow defines a variable called `message`, which is printed using string-interpolation. Any expression
wrapped in parenthesis (that is in a command such as `echo`) will be evaluated, converted to a string, and
finally be passed to the command, in this case, `echo`. Think of this like f-strings in Python, or string interpolation
in C#, except they only apply to commands.

For more information on the `let` expression click [here](./let-expr.md).

### Environment Variables

Cicada supports repository-scoped environment variables as well! We do not support secrets yet, and as such,
only non-sensitive data should be used in environment variables.

Here's an example of environment variables in action:

```
let username = env.USERNAME

shell useradd (username)
shell su (username)

make
```

This workflow will create a new user, switch to that user, and run some tests via `make`. The user's username will
be whatever the environment variable `USERNAME` is set to.

## What's Next

Now that you've familiarized yourself with the basics of Cicada, click [here](./) to read more about the Cicada DSL.
