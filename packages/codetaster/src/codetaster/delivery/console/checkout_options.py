"""The arguments shared by commands that compare a checkout against its base."""

from pathlib import Path
from typing import Annotated

import typer
from safe_result import Err

from codetaster.delivery.console.conventions import codetaster_conventions
from codetaster.domain.application_services.load_configuration import (
    ConfigurationRequest,
    load_configuration,
)
from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    RevisionName,
    WorkingTreeState,
)
from codetaster.infrastructure.config_file_store.local import LocalConfigFileStore
from codetaster.infrastructure.environment_variables.os_environment import (
    OsEnvironmentVariables,
)

CheckoutArgument = Annotated[
    CheckoutPath,
    typer.Argument(
        parser=CheckoutPath,
        metavar="PATH",
        help="A repository checkout. Its project config is used.",
    ),
]

BaseOption = Annotated[
    RevisionName | None,
    typer.Option(
        "--base",
        parser=RevisionName,
        metavar="BRANCH",
        # Escaped, because Rich would read [review] as markup.
        help="Compare against this branch instead of \\[review] base_branch.",
        show_default=False,
    ),
]


def resolve_checkout(checkout: CheckoutPath) -> CheckoutPath:
    """The absolute checkout, or exit with a message if it is not a directory."""
    if not checkout.root.is_dir():
        message = f"{checkout} is not a directory"
        raise typer.BadParameter(message, param_hint="PATH")
    return CheckoutPath(checkout.root.resolve())


def load_checkout_configuration(checkout: CheckoutPath) -> Configuration:
    """The configuration for `checkout`, or exit with a message."""
    configuration = load_configuration(
        ConfigurationRequest(
            home=Location(Path.home()),
            working_directory=Location(checkout.root),
            conventions=codetaster_conventions(),
        ),
        LocalConfigFileStore(),
        OsEnvironmentVariables(),
    )
    if isinstance(configuration, Err):
        typer.echo(f"Error: invalid config file {configuration.error}", err=True)
        raise typer.Exit(code=1)
    return configuration.value


def warn_about_uncommitted_changes(working_tree: WorkingTreeState) -> None:
    if working_tree is WorkingTreeState.DIRTY:
        typer.echo(
            "Warning: the working tree has uncommitted changes. "
            "Only committed changes are checked.",
            err=True,
        )
