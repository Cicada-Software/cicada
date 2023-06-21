# Executors

An executor is something that runs a Cicada workflow. Currently there is only one supported
executor, the `remote-podman` executor. More executors are planned to be added in the future.

## `remote-podman` Executor (default)

This executor will create a new podman container using the image specified by the user (if
any), or `alpine` if none is specified. Any commands that need to be ran will be injected into
the container, and the responses will be streamed back to the server.

When the container for a workflow is being setup a few things will happen:

1. The Git repo for the workflow will be cloned
2. The branch/SHA that triggered the workflow will be checked out
3. The folder containing the repo gets mounted to `/tmp/{UUID}/` in the container

When running commands in the workflow, the current directory will be at the `/tmp/{UUID}/`
folder, unless a `cd` command is ran.
