# GitHub Pull Requests (codetaster)

A fork of [microsoft/vscode-pull-request-github](https://github.com/microsoft/vscode-pull-request-github) (MIT, see `LICENSE`) that groups a pull request's changed files by codetaster's review verdict. Its extension ID is `codetaster.vscode-pull-request-github`, so disable the upstream extension while using it.

## Upstream

Copied without history from tag `v0.162.0` (commit `b0ff780afcd13a9f818bdcab173003eaf8885f12`).

Left out of the copy: `documentation/`, `.readme/`, `.github/`, `.husky/`, `azure-pipeline.*.yml`, and upstream's `README.md`, which this file replaces.

Edits to upstream files:

- `package.json`: `publisher` is `codetaster`.
- `package.nls.json`: `displayName`.
- `src/constants.ts`: `EXTENSION_ID`.

Sync with upstream only when needed. Put codetaster changes in new files under `src/codetaster/`, and keep edits to upstream files to small hook points, listed above.

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
