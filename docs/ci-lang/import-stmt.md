# The `import` Statement

The `import` statement allows you to import modules into your Cicada workflow.

> Currently only `.ci` files inside the cloned repository can be imported, but a
> package manager and/or remote import mechanism will be added in the future.

To import files, type `import` and then the filename you want to import:

```
import some/folder/file.ci
```

This will run `some/folder/file.ci` and automatically make all its functions and variables
available via `file.some_variable`.

Here is a full example of a workflow importing another module:

```
# module.ci

def greet(name: string):
  echo Hello (name)!
```

```
# workflow.ci
on git.push

import module.ci

module.greet(event.author)
```

This workflow will, on `git.push`, import `module`, then greet the commit author.

## Restrictions

There are some restrictions on how files are imported:

* The filename must include the `.ci` file extension.
* The file must exist, otherwise the workflow fails.
* The filename must be a valid Cicada identifier. For example, `123` starts with a number, and thus would be invalid.

In addition, there are also restrictions on what imported modules are capable of:

* Imported modules do not have access to the `secret` and `env` global variables.
  To pass a secret/env var to code in a module, you will need to do so explicitly via a function argument.
  This is for security reasons, since importing a malicious module (directly or indirectly) should not
  automatically expose sensitive data like your secrets.

* The `cache`, `on`, `run_on`, and `title` statements are not usable in imported modules.
  This is because these statements only make sense when defined at the top level of a workflow.

* You cannot call functions annotated with `@workflow` in imported modules. Imported modules are still
  able to define functions annotated with `@workflow`, but the modules themselves cannot call them.
  The reason being is that sub-workflows should be defined in the root of the workflow and not be hidden
  in a library function.
