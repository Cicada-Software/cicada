# The `on` Statement

The `on` statement allows for only running a workflow when a certain event occurs. For example,
this could be a git push, an issue/PR being opened, etc. For a full list of available events and
available metadata, see the [event types](./event-types.md) docs.

Basic usage of the `on` statement looks like this:

```
on git.push

echo Hello world!
```

This will run "Hello world!" whenever a push event is received. You might not want to respond to all
git push events though. In those situations, you will need to use an `on` statement with a `where` clause:

```
on git.push where event.branch is "dev"

echo This will only run on the dev branch
```

As the `echo` command suggests, this workflow will only run when code is pushed to the `dev` branch.
The `event` variable is a globally-defined variable which includes the metadata associated with the
push event. The most important part about the `event` variable is that it works cross-platform: this means
that this workflow can be ran on GitHub and Gitlab, and the behaviour will be exactly the same!

Keep in mind that different events have different fields. To see a full breakdown of the available
events and their fields, see the [event types](./event-types.md) docs.

## Limitations

In order for Cicada to run your workflows properly, there are certain limitations to the `on` statement.

1. You cannot execute functions before the `on` statement. The following workflow is not valid:

```
echo Running before the on statement

on git.push
```

2. You cannot define multiple `on` statements. This feature might be added later, but does not exist yet.
