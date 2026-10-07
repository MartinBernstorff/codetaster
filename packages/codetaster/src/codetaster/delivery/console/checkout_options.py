"""The arguments shared by commands that compare a checkout against its base."""

from typing import Annotated

import typer

from codetaster.delivery.console.configuration_loading import (
    load_configuration_or_exit,
)
from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    RevisionName,
    WorkingTreeState,
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
    return load_configuration_or_exit(Location(checkout.root))


def warn_about_uncommitted_changes(working_tree: WorkingTreeState) -> None:
    if working_tree is WorkingTreeState.DIRTY:
        typer.echo(
            "Warning: the working tree has uncommitted changes. "
            "Only committed changes are checked.",
            err=True,
        )
