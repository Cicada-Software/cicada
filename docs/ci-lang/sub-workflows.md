# Sub-workflows

Sub-workflows are special functions that, when called, run concurrently in the background.

Here is an example of defining and using a sub-workflow:

```
on git.push

@workflow
fn test(version):
  echo Installing version (version)
  make install VERSION=(version)

  echo Running tests
  make test

test("1.0")
test("1.1")
test("1.2")
```

This code will create 4 workflows: The "root" workflow, which is created automatically, and 3 sub-workflows which
are spawned from the root workflow. When calling functions annotated with `@workflow`, the filesystem of root
workflow is copied to the sub-workflow, meaning that any setup or caching done before calling `test` will be
included in the sub-workflow.

When using sub-workflows, the session will be finished when all sub-workflows are finished executing.

## Limitations

Running processes are not preserved when creating sub-workflows, only the filesystem contents.
