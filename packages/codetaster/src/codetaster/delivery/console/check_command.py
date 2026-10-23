from enum import StrEnum
from typing import Annotated, override

import typer
from pydantic import ConfigDict, RootModel
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
from codetaster.domain.domain_model.review.adaptive_sampling import (
    AdaptiveSampling,
    CommentedFileCount,
    SamplingEvidence,
    ViewedFileCount,
)
from codetaster.domain.domain_model.review.needs_review_threshold import (
    NeedsReviewThreshold,
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


class SamplingSummary(RootModel[str]):
    """A line saying how the reviewer's evidence changed the sampling probability."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> SamplingSummary:
        return sampling_summary(AdaptiveSampling.fake())


@check_app.command("check")
def check_changes(
    checkout: CheckoutArgument,
    base: BaseOption = None,
    threshold: Annotated[
        NeedsReviewThreshold | None,
        typer.Option(
            "--needs-review-threshold",
            parser=lambda value: NeedsReviewThreshold(float(value)),
            metavar="RATING",
            help="The AI rating, from 0 to 1, at or above which a file needs "
            "review, instead of \\[review] needs_review_threshold.",
            show_default=False,
        ),
    ] = None,
    commented_files: Annotated[
        CommentedFileCount | None,
        typer.Option(
            "--commented-files",
            parser=lambda value: CommentedFileCount(int(value)),
            metavar="COUNT",
            help="How many sampled or needs-review files you commented on. Each "
            "raises the probability the other files are sampled at. 0 if not given.",
            show_default=False,
        ),
    ] = None,
    viewed_files: Annotated[
        ViewedFileCount | None,
        typer.Option(
            "--viewed-files",
            parser=lambda value: ViewedFileCount(int(value)),
            metavar="COUNT",
            help="How many sampled or needs-review files you viewed without "
            "commenting. Each lowers the sampling probability again, but never "
            "below \\[review] base_probability. 0 if not given.",
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
    """Decide which files changed since the merge base with the base need review.

    Files are rated from \\[review] ratings_path, if it exists and is valid; an
    invalid one is reported and leaves every file unrated. Files rated at or
    above --needs-review-threshold need review; other files are sampled at \\[review] base_probability,
    raised by --commented-files and lowered again by --viewed-files, weighed
    against \\[review] base_probability_weight. Only committed changes count. Exits 0 whatever the verdict, unless
    --fail-on-needs-review is given.
    """
    checkout = resolve_checkout(checkout)
    match check_committed_changes(
        CheckRequest(
            checkout=checkout,
            base_override=base,
            threshold_override=threshold,
            evidence=SamplingEvidence(
                commented_files=commented_files or CommentedFileCount(0),
                viewed_files=viewed_files or ViewedFileCount(0),
            ),
        ),
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
    if result.sampling.effective_probability() != result.sampling.base_probability:
        typer.echo(str(sampling_summary(result.sampling)), err=True)
    match output_format:
        case OutputFormat.JSON:
            typer.echo(report.model_dump_json(by_alias=True, indent=2))
    if fail_on_needs_review and result.verdict() is not Verdict.NO_REVIEW:
        raise typer.Exit(code=1)


def sampling_summary(sampling: AdaptiveSampling) -> SamplingSummary:
    evidence = sampling.evidence
    return SamplingSummary(
        f"Sampling at {sampling.effective_probability().root:.1%} instead of "
        f"{sampling.base_probability.root:.1%}: "
        f"{evidence.commented_files.root} commented, "
        f"{evidence.viewed_files.root} viewed."
    )
