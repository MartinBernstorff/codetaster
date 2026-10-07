from enum import StrEnum
from typing import Annotated

import typer
from safe_result import Err, Ok

from codetaster.delivery.console.check_report import check_report_from_result
from codetaster.delivery.console.checkout_options import (
    BaseOption,
    CheckoutArgument,
    load_checkout_configuration,
    resolve_checkout,
    warn_about_uncommitted_changes,
)
from codetaster.domain.application_services.check_committed_changes import (
    CheckRequest,
    check_committed_changes,
)
from codetaster.domain.domain_model.review.sampling import Verdict
from codetaster.infrastructure.committed_changes.git_committed_changes import (
    GitCommittedChanges,
)
from codetaster.infrastructure.ratings_file_store.local import LocalRatingsFileStore

# Added to the main app without a name, so `check` is a top-level command.
check_app = typer.Typer()


class OutputFormat(StrEnum):
    JSON = "json"


@check_app.command("check")
def check_changes(
    checkout: CheckoutArgument,
    base: BaseOption = None,
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
    """Decide which files changed since the merge base with the base need review.

    Files are rated from \\[review] ratings_path, if it exists and is valid; an
    invalid one is reported and leaves every file unrated. Only committed
    changes count. Exits 0 whatever the verdict, unless
    --fail-on-needs-review is given.
    """
    checkout = resolve_checkout(checkout)
    match check_committed_changes(
        CheckRequest(checkout=checkout, base_override=base),
        load_checkout_configuration(checkout),
        GitCommittedChanges(),
        LocalRatingsFileStore(),
    ):
        case Ok(result):
            pass
        case Err(error):
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(code=1)
    warn_about_uncommitted_changes(result.working_tree)
    report = check_report_from_result(result)
    if report.ratings_error is not None:
        typer.echo(f"Warning: {report.ratings_error}\nEvery file is unrated.", err=True)
    match output_format:
        case OutputFormat.JSON:
            typer.echo(report.model_dump_json(by_alias=True, indent=2))
    if fail_on_needs_review and result.verdict() is not Verdict.NO_REVIEW:
        raise typer.Exit(code=1)
