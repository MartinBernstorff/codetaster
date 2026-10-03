import logging
from pathlib import Path
from typing import Annotated

import typer
from safe_result import Err, Ok, Result

from codetaster_cli.domain.application_services.set_up_checkout import set_up_checkout
from codetaster_cli.domain.application_services.tear_down_checkout import (
    tear_down_checkout,
)
from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.infrastructure.git_hooks.lefthook_git_hooks import (
    LefthookGitHooks,
)
from codetaster_cli.infrastructure.git_worktrees.git_cli_worktrees import (
    GitCliWorktrees,
)
from codetaster_cli.infrastructure.python_environment.uv_python_environment import (
    UvPythonEnvironment,
)
from codetaster_cli.infrastructure.task_cache.moon_task_cache import MoonTaskCache
from codetaster_cli.infrastructure.toolchain.proto_toolchain import ProtoToolchain

app = typer.Typer(no_args_is_help=True, help="Developer utilities for codetaster.")


@app.callback()
def configure_logging(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Only log warnings and errors.")
    ] = False,
) -> None:
    logging.basicConfig(
        level=logging.WARNING if quiet else logging.INFO, format="%(message)s"
    )


@app.command()
def setup() -> None:
    """Make the current checkout ready to work in.

    Runs `proto install`, `uv sync --locked` and `uv run lefthook install`.
    Safe to re-run.
    """
    _ = exit_on_error(
        set_up_checkout(
            ProtoToolchain(),
            UvPythonEnvironment(),
            LefthookGitHooks(),
            CheckoutPath(Path.cwd()),
        )
    )


@app.command()
def teardown() -> None:
    """Undo `setup` for the current checkout.

    Removes `.venv` and the moon cache. Uninstalls the git hooks only if no other
    worktree of this repository remains, since all worktrees share them.
    """
    _ = exit_on_error(
        tear_down_checkout(
            GitCliWorktrees(),
            LefthookGitHooks(),
            UvPythonEnvironment(),
            MoonTaskCache(),
            CheckoutPath(Path.cwd()),
        )
    )


def exit_on_error[T](result: Result[T, Exception]) -> T:
    """Turn an error result into a message on stderr and exit code 1."""
    match result:
        case Ok(value):
            return value
        case Err(error):
            logging.getLogger(__name__).error("%s", error)
            raise typer.Exit(code=1)
