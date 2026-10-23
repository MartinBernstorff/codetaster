# GitHub Pull Requests (codetaster)

A fork of [microsoft/vscode-pull-request-github](https://github.com/microsoft/vscode-pull-request-github) (MIT, see `LICENSE`) that groups a pull request's changed files by the categories of codetaster's AI ratings and marks each with its review verdict. Its extension ID is `codetaster.vscode-pull-request-github`, so disable the upstream extension while using it.

## Upstream

Copied without history from tag `v0.162.0` (commit `b0ff780afcd13a9f818bdcab173003eaf8885f12`).

Left out of the copy: `documentation/`, `.readme/`, `.github/`, `.husky/`, `azure-pipeline.*.yml`, and upstream's `README.md`, which this file replaces.

Edits to upstream files:

- `package.json`: `publisher` is `codetaster`; the `codetaster.executablePath`, `codetaster.needsReviewThreshold` and `codetaster.openOnStartup` settings and the `codetaster.refreshCheck` command and its view title buttons. The `github-pull-request` view container is named "codetaster" with the `$(eye)` icon, its "Changes In Pull Request" view is visible without a pull request, it has welcome content for no folder, no git repository and signed out, and the "Active Pull Request" loading view is removed.
- `package.nls.json`: `displayName`, the container name and the welcome content.
- `src/constants.ts`: `EXTENSION_ID`.
- `src/extension.ts`: calls `registerCodetaster`; `github.api.preloadPullRequest` focuses the changes view instead of the removed loading view.
- `src/github/utils.ts`: `getCommentCollapsibleState` expands threads with draft comments (see `draftThreadExpansion`).
- `src/view/prChangesTreeDataProvider.ts`: without a pull request, shows `codetasterNoPullRequestNodes`, and refreshes on `refreshOnNoPullRequestInputs`.
- `src/view/reviewManager.ts`: reports why the branch shows no pull request with `updateReviewStatus`.
- `src/view/treeNodes/filesCategoryNode.ts`, `src/view/treeNodes/pullRequestNode.ts`: use `codetasterFileNodes` for the checked-out PR's file list, falling back to upstream's list otherwise, and refresh on `codetasterChecks.onDidRefresh`. `filesCategoryNode.ts` also passes itself to show the needs-review share as its description.
- `src/view/treeNodes/repositoryChangesNode.ts`: passes the `FolderRepositoryManager` to `FilesCategoryNode`.
- `webpack.config.js`: `child_process` is empty in the web extension host.

Sync with upstream only when needed. Put codetaster changes in new files under `src/codetaster/`, and keep edits to upstream files to small hook points, listed above.

## codetaster grouping

When the checked-out PR's file list loads, the extension runs `codetaster check <checkout> --base <PR base> --format json` in the local checkout and groups the files by the category of their AI rating, as "<category> (n)", in the order the ratings file lists its categories. The base is the remote-tracking branch of the PR's base branch, or the branch name if no remote points at the base repository. Each file's icon shows its verdict: a green circle for needs review, a yellow circle for sampled, and the usual file-type icon for no review. The file's hover states the verdict and its AI rating. A category whose files all need no review starts collapsed. Above the categories, a "Summary" node opens the overview: the PR summary from the ratings file, then each category and its description, as a Markdown preview. The overview opens by itself the first time a PR has one in a session. Without a valid ratings file there is no summary node. The "Files" node's description gives the needs-review rule and the sampling probability, e.g. "needs review = rating ≥ 0.6 · Sampling 10% → 18% (1 commented, 5 viewed)". Each needs-review or sampled file you commented on (a thread you started, draft or submitted, resolved or not) raises the probability the remaining files are sampled at, and each one you marked viewed without commenting lowers it again, never below `[review] base_probability`; the extension passes these counts to the check as `--commented-files` and `--viewed-files`, and files that become sampled move into the sampled verdict. A file keeps counting for the rest of the session once it has been needs-review or sampled. Files the check lists without a rating appear last, under "Unrated (n)". Other PR files the check does not list appear first, under "Not in codetaster check (n)", with a question-mark icon. Other PRs show upstream's file list, and codetaster does not run for them. If the check fails, the view shows the error and no files, and the next refresh retries it. If the ratings file is invalid, a warning above the groups says so and every file is unrated. The check re-runs when the PR's head or file list changes, the local HEAD commit changes, your comment threads or viewed files change the counts, a `.codetaster/ratings.json` file changes (the default `[review] ratings_path`; a custom path is not watched), or on "codetaster: Refresh Check". `codetaster.executablePath` sets the executable (default: `codetaster` on PATH).

## Sidebar

The codetaster container is always in the activity bar. While a repository looks for its branch's pull request, and while a PR's first check runs, the view shows a single placeholder. Later re-runs of the check, e.g. after a local commit, keep showing the last report until they finish. Without a pull request, the view says why: no folder, no git repository, no GitHub remote, signed out (with a sign-in button), no open pull request for the branch, the branch is ignored, the pull request could not be loaded, or it is closed or merged. `codetaster.openOnStartup` (default off) opens the container when VS Code starts.

## Draft comments

A comment thread with a draft (pending review) comment opens expanded, even when resolved and whatever `githubPullRequests.commentExpandState` says. After the review is submitted, the thread stays expanded until it is resolved or unresolved.

## Tasks

Run from the repo root:

| Task | Does |
| --- | --- |
| `moon run vscode-extension:build` | Installs dependencies and bundles the extension into `dist/` |
| `moon run vscode-extension:package` | Writes `codetaster.vsix` |
| `moon run vscode-extension:test` | Runs codetaster's tests (`src/codetaster/**/*.test.ts`) with mocha. Upstream's suite is not run. |
| `moon run vscode-extension:full` | All of the above. CI runs this through `moon ci :full`. |

## Install

From the repo root, run `uv run codetaster-manage install`, then restart VS Code. It first installs the codetaster CLI globally with `uv tool install --force --reinstall packages/codetaster`, so the extension never runs a stale CLI. It then packages the extension with `moon run vscode-extension:package`, enables its proposed APIs (below) and installs the VSIX with `code --install-extension`. It needs the `code` command on `PATH`.

## Proposed API

The extension uses VS Code proposed APIs (`enabledApiProposals` in `package.json`). VS Code only allows these for allowlisted extension IDs, which this fork is not. `install` adds the ID to `enable-proposed-api` in VS Code's `argv.json` (`~/.vscode/argv.json`, Command Palette: "Preferences: Configure Runtime Arguments"). To do it by hand, add:

```json
"enable-proposed-api": ["codetaster.vscode-pull-request-github"]
```
