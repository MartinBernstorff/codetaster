import logging
from typing import Annotated

import typer

from codetaster.delivery.console.config_command import config_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(config_app, name="config")


@app.callback()
def configure_logging(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Only log warnings and errors.")
    ] = False,
) -> None:
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO)


@app.command()
def hello() -> None:
    logging.getLogger(__name__).info("Hello from codetaster")
