# `codetaster check --format json`

`codetaster check <path>` decides which files changed on the current branch need human review. With `--format json`, it prints one JSON object to stdout. Warnings and errors go to stderr.

## Example

```json
{
  "schema_version": 1,
  "needs_review": true,
  "override_label_applied": false,
  "base": {
    "ref": "main",
    "merge_base": "e3f8894b4da91eca13fe184d20e067e9e78b7004"
  },
  "head": {
    "commit": "79e0b79d50b48a3588d5d1a0a8956bd4e52970ba"
  },
  "needs-review": [
    {
      "path": "src/new_name.py",
      "previous_path": "src/old_name.py",
      "change_type": "renamed",
      "base_probability": 0.3,
      "probability": 0.3,
      "draw": 0.1184
    }
  ],
  "no-review": []
}
```

## Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | `1`. Bumped when a field is removed or changes meaning. New fields can appear without a bump, so ignore fields you don't know. |
| `needs_review` | boolean | `true` if any file is in `needs-review`. |
| `override_label_applied` | boolean | `true` if a PR label forced every file into `needs-review`. Always `false` for now. |
| `base.ref` | string | The base branch: `--base` if given, otherwise `base_branch` from `[review]` in the project config. |
| `base.merge_base` | string | The SHA of the merge base of `base.ref` and HEAD. The change is `merge_base..head`. |
| `head.commit` | string | The SHA of HEAD. Uncommitted changes are not included. |
| `needs-review` | array of files | The files that need human review. |
| `no-review` | array of files | The files that don't. |

Each file has:

| Field | Type | Meaning |
| --- | --- | --- |
| `path` | string | Path from the repository root, with `/` separators. For a renamed file, its new path. For a deleted file, its old path. |
| `previous_path` | string or null | The old path of a renamed file. `null` for other change types. |
| `change_type` | string | `added`, `modified`, `deleted` or `renamed`. |
| `base_probability` | number | `base_probability` from `[review]`. |
| `probability` | number | The probability, from 0 to 1, that this file needs review. |
| `draw` | number | The file's random number, from 0 inclusive to 1 exclusive. The file needs review if `draw < probability`. |

Files are ordered by path.

## The draw

The draw is SHA-256 over `[before_path, before_blob, after_path, after_blob]`, encoded as JSON with `null` for a side that doesn't exist (the before side of an added file, or the after side of a deleted one). The blobs are git's blob SHAs. The first 53 bits of the digest, divided by 2^53, give the draw.

So the draw is the same on every machine, and it changes only when that file's change does. Adding an empty commit, or changing other files, does not re-draw it.

## Exit codes

| Code | When |
| --- | --- |
| 0 | The check ran, whatever the verdict. |
| 1 | An error, such as a missing `[review]` section or an unknown base branch. Or, with `--fail-on-needs-review`, a file needs review. |
| 2 | Invalid arguments, such as a `<path>` that is not a directory. |
