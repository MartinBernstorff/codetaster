# codetaster

A Python CLI.

## Layout

A uv workspace with three packages under `packages/`:

| Package | Holds |
| --- | --- |
| `codetaster` | The app and its `codetaster` CLI. |
| `codetaster-lib` | Language extensions. Anything may depend on it; it depends on nothing internal. |
| `codetaster-cli` | Developer utilities for this repo, e.g. `codetaster-cli setup`. |

`codetaster` and `codetaster-cli` follow the same layering, enforced by `tach`:

```
delivery/console            Typer commands; the composition root that wires adapters in
domain/features         ->  application_services
domain/application_services -> secondary_ports | domain_model
domain/secondary_ports  ->  domain_model   (Protocols for anything external)
domain/domain_model         entities and value objects
infrastructure          ->  secondary_ports | domain_model
```

- The domain never imports infrastructure or delivery.
- Use-cases in `application_services` never import each other; shared logic belongs in a domain service.
- Each secondary port has a real implementation and a fake in `infrastructure`, plus contract tests there that run against both.

## Setup

A fresh clone or worktree needs `uv` and [proto](https://moonrepo.dev/docs/proto/install). Then run:

```
uv run codetaster-cli setup   # proto install, uv sync, lefthook install
```

## Python

- **Never use primitives as function parameters, fields or return types.** Wrap them in a Pydantic `RootModel`: `BranchName` says what a `str` is. Enforced by `moon run :noprim`. The only exemption is `bool` options on Typer commands.
- **Every domain model and RootModel has a `@staticmethod fake()`** that returns an instance with a default for every value. Aggregates build their defaults by calling `.fake()` on their members.
- **No `tests/` folder.** Tests live next to the code they test, as `test_<module>.py`.
- **When a module needs multiple files, make it a folder.** Keep `__init__.py` files empty.
- **Never maintain `__all__`.** Import from the defining module.
- **Use nominal typing.** A class implementing a Protocol also inherits from it.
- **Return errors as values** with [safe-result](https://github.com/overflowy/safe-result). The delivery layer turns an error into a message and a non-zero exit.
- **No single-word free functions.** `load()` is unreadable at the call site; `load_project_config()` is not.
- **Avoid constants.** Before adding one, consider whether it should be an argument supplied by the caller.
- **Secrets** come from environment variables or `~/.config/codetaster/`. **Developer config** lives in `~/.config/codetaster/`. **Project config** is found by searching from `$PWD` upward, stopping at the directory containing `.git`.

## Moon

Always run tasks through moon, never the tool directly: `moon run :test`, not `pytest`. Moon runs task dependencies and caches results.

| Task | Does |
| --- | --- |
| `moon run :phase-1` | Fast checks for pre-commit: fixes lint and formatting, then typecheck, modularity, noprim, actionlint |
| `moon run :full` | Every check, without fixing. CI runs this. |
| `moon run :test` | pytest (parallel, random order) |
| `moon run :lint` / `:lint-fix` | ruff check |
| `moon run :format-check` / `:format` | ruff format |
| `moon run :typecheck` | pyrefly |
| `moon run :modularity` | tach check + tach check-external |
| `moon run :noprim` | noprim |
| `moon run :actionlint` | actionlint over `.github/workflows/` |

A task's `inputs` must include every file it reads. Otherwise moon replays a stale cached result.

## Tooling

- Tool settings live in each tool's own file (`ruff.toml`, `pyrefly.toml`, `tach.toml`, `pytest.toml`, `noprim.toml`), not in `pyproject.toml`.
- Commits are validated automatically by lefthook pre-commit hooks (`lefthook.yml`), which run `moon run :phase-1`.
- PRs are squash-merged once CI passes. Renovate opens and auto-merges dependency updates on weekday mornings.
