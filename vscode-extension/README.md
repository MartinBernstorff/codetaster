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
- `src/view/treeNodes/filesCategoryNode.ts`, `src/view/treeNodes/pullRequestNode.ts`: build the file list with `codetasterFileNodes`, and refresh on `codetasterChecks.onDidRefresh`.
- `src/view/treeNodes/repositoryChangesNode.ts`: passes the checkout root to `FilesCategoryNode`.
- `webpack.config.js`: `child_process` is empty in the web extension host.

Sync with upstream only when needed. Put codetaster changes in new files under `src/codetaster/`, and keep edits to upstream files to small hook points, listed above.

## codetaster grouping

When a PR's file list loads, the extension runs `codetaster check <checkout> --format json` in the local checkout and shows the files under "Needs review (n)", "Sampled (n)" and "No review (n)". PR files the check does not list appear under "Not in codetaster check (n)". If the check fails, the view shows the error and no files. The check re-runs when the PR's head or file list changes, or on "codetaster: Refresh Check". `codetaster.executablePath` sets the executable (default: `codetaster` on PATH).

## Tasks

Run from the repo root:

| Task | Does |
| --- | --- |
| `moon run vscode-extension:build` | Installs dependencies and bundles the extension into `dist/` |
| `moon run vscode-extension:package` | Writes `codetaster.vsix` |
| `moon run vscode-extension:test` | Runs codetaster's tests (`src/codetaster/**/*.test.ts`) with mocha. Upstream's suite is not run. |
| `moon run vscode-extension:full` | All of the above. CI runs this through `moon ci :full`. |

## Proposed API

The extension uses VS Code proposed APIs (`enabledApiProposals` in `package.json`). VS Code only allows these for allowlisted extension IDs, which this fork is not. To enable them, add the ID to `enable-proposed-api` in VS Code's `argv.json` (Command Palette: "Preferences: Configure Runtime Arguments"):

```json
"enable-proposed-api": ["codetaster.vscode-pull-request-github"]
```
