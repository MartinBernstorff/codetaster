import shlex
from enum import StrEnum

import typer
from pydantic import RootModel
from safe_result import Err, Ok

from codetaster.delivery.console.checkout_options import (
    BaseOption,
    CheckoutArgument,
    load_checkout_configuration,
    resolve_checkout,
    warn_about_uncommitted_changes,
)
from codetaster.domain.application_services.create_ratings_template import (
    RatingsTemplateRequest,
    RatingsTemplateResult,
    create_ratings_template,
)
from codetaster.domain.application_services.validate_ratings_file import (
    RatingsValidationRequest,
    validate_ratings_file,
)
from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.review.changes import RevisionName
from codetaster.domain.domain_model.review.ratings_validation import (
    DuplicateRating,
    InvalidRatingsFile,
    MissingRatingsFile,
    RatingProblem,
    StaleRating,
    UnknownRating,
    UnratedFile,
)
from codetaster.infrastructure.committed_changes.git_committed_changes import (
    GitCommittedChanges,
)
from codetaster.infrastructure.ratings_file_store.local import LocalRatingsFileStore

ratings_app = typer.Typer(
    no_args_is_help=True, help="Rate how likely changed files are to need review."
)


@ratings_app.command("template")
def print_ratings_template(
    checkout: CheckoutArgument,
    base: BaseOption = None,
) -> None:
    """Print instructions for a coding agent, and a template to rate every changed file.

    The agent fills in the template and writes it to \\[review] ratings_path.
    """
    checkout = resolve_checkout(checkout)
    match create_ratings_template(
        RatingsTemplateRequest(checkout=checkout, base_override=base),
        load_checkout_configuration(checkout),
        GitCommittedChanges(),
    ):
        case Ok(result):
            pass
        case Err(error):
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(code=1)
    warn_about_uncommitted_changes(result.working_tree)
    echo_rating_instructions(result, checkout, base)
    typer.echo("")
    typer.echo(result.template.model_dump_json(indent=2))


def echo_rating_instructions(
    result: RatingsTemplateResult, checkout: CheckoutPath, base: RevisionName | None
) -> None:
    base_probability = result.base_probability.root
    location = result.ratings_location
    validate = ratings_command_line(RatingsSubcommand.VALIDATE, checkout, base)
    typer.echo(f"""\
Rate how likely each file changed on this branch is to need human review.

codetaster decides which changed files a human reviews. Each file gets a random
draw from 0 to 1. A file needs review if its draw is below your rating, and is
sampled for review if its draw is below the base probability, {base_probability}.
So a rating can only raise a file's chance of review: a rating below
{base_probability} does not lower it.

Fill in every entry of the JSON template below:
- "probability": from 0 to 1, how likely the change to this file is to need
  human review. Rate risky, subtle or hard-to-undo changes high, and mechanical
  or well-tested ones low.
- "reason": one sentence on why.
- Leave "path" and "blob" as they are. A rating applies only to the file
  content with that blob SHA, so editing the file afterwards makes the rating
  stale. A deleted file has "blob": null.

Write the filled-in JSON to {location.root}
Then run this, and fix any problems it reports:

    {validate.root}""")


@ratings_app.command("validate")
def validate_ratings(
    checkout: CheckoutArgument,
    base: BaseOption = None,
) -> None:
    """Check the ratings file rates every changed file once, and nothing else.

    Exits 1 and lists every problem if it does not.
    """
    checkout = resolve_checkout(checkout)
    match validate_ratings_file(
        RatingsValidationRequest(checkout=checkout, base_override=base),
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
    problems = result.problems.root
    if not problems:
        typer.echo(f"{result.location.root} rates every changed file.")
        return
    typer.echo(
        f"Error: the ratings file {result.location.root} is not valid:", err=True
    )
    for problem in problems:
        typer.echo(
            f"- {describe_rating_problem(problem, checkout, base).root}", err=True
        )
    raise typer.Exit(code=1)


class RatingProblemDescription(RootModel[str]):
    """What is wrong with a ratings file, and how to fix it."""

    @staticmethod
    def fake() -> RatingProblemDescription:
        return RatingProblemDescription("src/module.py has no rating.")


def describe_rating_problem(
    problem: RatingProblem, checkout: CheckoutPath, base: RevisionName | None
) -> RatingProblemDescription:
    """What is wrong, and how a coding agent can fix it.

    File versions are shown as they are written in the ratings file.
    """
    match problem:
        case MissingRatingsFile(location=location):
            template = ratings_command_line(RatingsSubcommand.TEMPLATE, checkout, base)
            return RatingProblemDescription(
                f"There is no ratings file at {location.root}. Run `{template.root}`, "
                "fill in the template and write it there."
            )
        case InvalidRatingsFile(reason=reason):
            details = reason.root.replace("\n", "\n  ")
            return RatingProblemDescription(
                f"It does not match the ratings format:\n  {details}"
            )
        case UnratedFile(target=target):
            return RatingProblemDescription(
                f"{target.path} has no rating. "
                f"Add a rating for {target.model_dump_json()}."
            )
        case StaleRating(rating=rating, current=current):
            return RatingProblemDescription(
                f"The rating for {rating.model_dump_json()} is for another version "
                f"of {rating.path}. Re-rate the file as it is now, "
                f"{current.model_dump_json()}."
            )
        case UnknownRating(rating=rating):
            return RatingProblemDescription(
                f"{rating.path} is not changed on this branch. Remove its rating."
            )
        case DuplicateRating(target=target):
            return RatingProblemDescription(
                f"{target.model_dump_json()} has more than one rating. Keep one."
            )


class RatingsSubcommand(StrEnum):
    TEMPLATE = "template"
    VALIDATE = "validate"


class CommandLine(RootModel[str]):
    @staticmethod
    def fake() -> CommandLine:
        return CommandLine("codetaster ratings validate .")


def ratings_command_line(
    subcommand: RatingsSubcommand, checkout: CheckoutPath, base: RevisionName | None
) -> CommandLine:
    """The shell command to run `subcommand` on `checkout` against `base`."""
    return CommandLine(
        shlex.join(
            [
                "codetaster",
                "ratings",
                subcommand,
                str(checkout.root),
                *(["--base", str(base)] if base is not None else []),
            ]
        )
    )
