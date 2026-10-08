# GitHub Pull Requests (codetaster)

A fork of [microsoft/vscode-pull-request-github](https://github.com/microsoft/vscode-pull-request-github) (MIT, see `LICENSE`) that groups a pull request's changed files by codetaster's review verdict. Its extension ID is `codetaster.vscode-pull-request-github`, so disable the upstream extension while using it.

## Upstream

Copied without history from tag `v0.162.0` (commit `b0ff780afcd13a9f818bdcab173003eaf8885f12`).

Left out of the copy: `documentation/`, `.readme/`, `.github/`, `.husky/`, `azure-pipeline.*.yml`, and upstream's `README.md`, which this file replaces.

Edits to upstream files:

- `package.json`: `publisher` is `codetaster`; the `codetaster.executablePath` setting and the `codetaster.refreshCheck` command and its view title buttons.
- `package.nls.json`: `displayName`.
- `src/constants.ts`: `EXTENSION_ID`.
- `src/extension.ts`: calls `registerCodetaster`.
- `src/view/treeNodes/filesCategoryNode.ts`, `src/view/treeNodes/pullRequestNode.ts`: use `codetasterFileNodes` for the checked-out PR's file list, falling back to upstream's list otherwise, and refresh on `codetasterChecks.onDidRefresh`. `pullRequestNode.ts` also refreshes on `onDidChangeReviewThreads`.
- `src/view/treeNodes/repositoryChangesNode.ts`: passes the `FolderRepositoryManager` to `FilesCategoryNode`.
- `webpack.config.js`: `child_process` is empty in the web extension host.

Sync with upstream only when needed. Put codetaster changes in new files under `src/codetaster/`, and keep edits to upstream files to small hook points, listed above.

## codetaster grouping

When the checked-out PR's file list loads, the extension runs `codetaster check <checkout> --base <PR base> --format json` in the local checkout and shows the files under "Needs review (n)", "Sampled (n)" and "No review (n)". The base is the remote-tracking branch of the PR's base branch, or the branch name if no remote points at the base repository. Files with an unresolved GitHub review thread are under "Needs review", whatever the check says. Other PR files the check does not list appear first, under "Not in codetaster check (n)". Other PRs show upstream's file list, and codetaster does not run for them. If the check fails, the view shows the error and no files, and the next refresh retries it. If the ratings file is invalid, a warning above the groups says so and every file is unrated. The check re-runs when the PR's head or file list changes, the local HEAD commit changes, a `.codetaster/ratings.json` file changes (the default `[review] ratings_path`; a custom path is not watched), or on "codetaster: Refresh Check". `codetaster.executablePath` sets the executable (default: `codetaster` on PATH).

## Tasks

Run from the repo root:

| Task | Does |
| --- | --- |
| `moon run vscode-extension:build` | Installs dependencies and bundles the extension into `dist/` |
| `moon run vscode-extension:package` | Writes `codetaster.vsix` |
| `moon run vscode-extension:test` | Runs codetaster's tests (`src/codetaster/**/*.test.ts`) with mocha. Upstream's suite is not run. |
| `moon run vscode-extension:full` | All of the above. CI runs this through `moon ci :full`. |

## Install

From the repo root, run `uv run codetaster-manage install-extension`, then restart VS Code. It packages the extension with `moon run vscode-extension:package`, enables its proposed APIs (below) and installs the VSIX with `code --install-extension`. It needs the `code` command on `PATH`.

## Proposed API

The extension uses VS Code proposed APIs (`enabledApiProposals` in `package.json`). VS Code only allows these for allowlisted extension IDs, which this fork is not. `install-extension` adds the ID to `enable-proposed-api` in VS Code's `argv.json` (`~/.vscode/argv.json`, Command Palette: "Preferences: Configure Runtime Arguments"). To do it by hand, add:

```json
"enable-proposed-api": ["codetaster.vscode-pull-request-github"]
```
