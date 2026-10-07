import shlex

import typer
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
from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.review.changes import RevisionName
from codetaster.domain.domain_model.review.ratings import ratings_file_location
from codetaster.infrastructure.committed_changes.git_committed_changes import (
    GitCommittedChanges,
)

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
    location = ratings_file_location(checkout, result.ratings_path)
    validate = shlex.join(
        [
            "codetaster",
            "ratings",
            "validate",
            str(checkout.root),
            *(["--base", str(base)] if base is not None else []),
        ]
    )
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

    {validate}""")
