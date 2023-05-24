# The `run_on` Statement

The `run_on` statement allows you to tell Cicada which operating system to run your workflows on.
Cicada Currently supports [OCI images](https://opencontainers.org/), meaning you can use any image
you like as the basis for your workflow.

The basic syntax of the `run_on` statement looks like this:

```
run_on image alpine:3.18
```

Now when Cicada runs this workflow, it will run it using the `alpine` version 3.18 image.
It is recommended that you always use a version for your images to allow for Cicada to better
cache your container images.

By default, Cicada uses the `docker.io` registry. To use a different registry, use the fully
qualified registry when specifying the image:

```
run_on image docker.io/alpine:3.18
```

## Restrictions

The `run_on` statement is only allowed in certain places. Essentially, for Cicada to be able to
detect what image to run your workflow in, the `run_on` statement needs to be near the top of the
file before any commands have been ran (since they would need to be ran on a computer).

The following are examples of invalid usage of the `run_on` statement:

```
# Ok, defined near the top of the file
run_on image alpine

# Invalid, `run_on` can only be specified once
run_on image ubuntu

if true:
  # Invalid, `run_on` must be defined at the top level
  run_on image alpine

echo hello world!

# Invalid, `run_on` cannot be used after running a command
run_on image alpine
```
