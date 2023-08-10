# Built-in Functions

## `hashOf`

Hash 1 or more files into a single hash. This function is useful for generating
cache keys to detect when a file (or many files) have changed.

Things to note about the `hashOf` function:

* File globs are supported, so `file.*` will expand to all files starting with `file.`.
* Every file explicitly passed (ie, not a glob) must exist. If a passed file doesn't exist, the workflow fails.
* After all globs (if any) are expanded, the file list is sorted before hashing.

Examples:

```
let hash = hashOf("package.json")

let hash = hashOf("docs/**/*.md")

let hash = hashOf("file1", "file2")
```
