from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from safe_result import Err, Ok

from codetaster.delivery.console.check_report import check_report_from_result
from codetaster.delivery.console.conventions import codetaster_conventions
from codetaster.domain.application_services.check_committed_changes import (
    CheckRequest,
    check_committed_changes,
)
from codetaster.domain.application_services.load_configuration import (
    ConfigurationRequest,
    load_configuration,
)
from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.sampling import Verdict
from codetaster.infrastructure.committed_changes.git_committed_changes import (
    GitCommittedChanges,
)
from codetaster.infrastructure.config_file_store.local import LocalConfigFileStore
from codetaster.infrastructure.environment_variables.os_environment import (
    OsEnvironmentVariables,
)

# Added to the main app without a name, so `check` is a top-level command.
check_app = typer.Typer()


class OutputFormat(StrEnum):
    JSON = "json"


@check_app.command("check")
def check_changes(
    checkout: Annotated[
        CheckoutPath,
        typer.Argument(
            parser=CheckoutPath,
            metavar="PATH",
            help="A repository checkout. Its project config is used.",
        ),
    ],
    base: Annotated[
        RevisionName | None,
        typer.Option(
            "--base",
            parser=RevisionName,
            metavar="BRANCH",
            # Escaped, because Rich would read [review] as markup.
            help="Compare against this branch instead of \\[review] base_branch.",
            show_default=False,
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat, typer.Option("--format", help="How to print the result.")
    ] = OutputFormat.JSON,
    fail_on_needs_review: Annotated[
        bool,
        typer.Option(
            "--fail-on-needs-review",
            help="Exit 1 if any file is in needs-review or sampled.",
        ),
    ] = False,
) -> None:
    """Sample which files changed since the merge base with the base need review.

    Only committed changes count. Exits 0 whatever the verdict, unless
    --fail-on-needs-review is given.
    """
    if not checkout.root.is_dir():
        message = f"{checkout} is not a directory"
        raise typer.BadParameter(message, param_hint="PATH")
    checkout = CheckoutPath(checkout.root.resolve())
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
    match check_committed_changes(
        CheckRequest(checkout=checkout, base_override=base),
        configuration.value,
        GitCommittedChanges(),
    ):
        case Ok(result):
            pass
        case Err(error):
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(code=1)
    if result.working_tree is WorkingTreeState.DIRTY:
        typer.echo(
            "Warning: the working tree has uncommitted changes. "
            "Only committed changes are checked.",
            err=True,
        )
    match output_format:
        case OutputFormat.JSON:
            typer.echo(
                check_report_from_result(result).model_dump_json(
                    by_alias=True, indent=2
                )
            )
    if fail_on_needs_review and result.verdict() is not Verdict.NO_REVIEW:
        raise typer.Exit(code=1)
