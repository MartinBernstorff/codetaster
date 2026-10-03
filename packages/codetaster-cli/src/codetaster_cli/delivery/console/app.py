import logging
from pathlib import Path
from typing import Annotated

import typer
from safe_result import Err, Ok, Result

from codetaster_cli.domain.application_services.set_up_checkout import set_up_checkout
from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.infrastructure.command_runner.subprocess_command_runner import (
    SubprocessCommandRunner,
)

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
        set_up_checkout(SubprocessCommandRunner(), CheckoutPath(Path.cwd()))
    )


def exit_on_error[T](result: Result[T, Exception]) -> T:
    """Turn an error result into a message on stderr and exit code 1."""
    match result:
        case Ok(value):
            return value
        case Err(error):
            logging.getLogger(__name__).error("%s", error)
            raise typer.Exit(code=1)
