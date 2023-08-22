# Caching

Caching files can speed up your automation workflows by reducing the amount of time spent recompiling
or downloading resources that can be shared across many workflow runs.

Here is an example of how to use caching might be used in a NodeJS application:

```
on git.push

cache node_modules using hashOf("package.json", "package-lock.json")

shell npm i
```

In the above workflow we hash the `package.json` and `package-lock.json` files and use that as a
key for retrieving our cache. If the cache key already exists, the specified files will be restored.
If not, the files will be uploaded after the workflow finishes, but only if the workflow finished
successfully.

Keep in mind that caches will expire after 14 days. Users cannot change this (yet).

## Limitations

Caching is an experimental feature right now, so there are some limits to what you can do:

* Each workflow file can only have one `cache` command.
* Cache key:
  * Cannot be empty.
  * Cannot contain the following characters: `:"'<>&+=/\`.
  * Must be 256 characters or less.
* Cached files:
  * Total file size must be less than 250MB before compression.
  * Only files from the cloned repository folder can be cached. For example, `/` and `~/` cannot be cached. This includes symlinks to outside of the repository folder.
