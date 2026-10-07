from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.errors import (
    MissingReviewSettingsError,
)
from codetaster.domain.domain_model.review.changes import (
    RepositoryPath,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.secondary_ports.committed_changes import (
    ChangeReadError,
    CommittedChanges,
)


class RatingsTemplateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkout: CheckoutPath
    base_override: RevisionName | None

    @staticmethod
    def fake() -> RatingsTemplateRequest:
        return RatingsTemplateRequest(checkout=CheckoutPath.fake(), base_override=None)


class RatingsTemplateResult(BaseModel):
    """The template, and the review settings an agent needs to fill it in."""

    model_config = ConfigDict(frozen=True)

    template: RatingsTemplate
    ratings_path: RepositoryPath
    base_probability: Probability
    working_tree: WorkingTreeState

    @staticmethod
    def fake() -> RatingsTemplateResult:
        return RatingsTemplateResult(
            template=RatingsTemplate.fake(),
            ratings_path=RepositoryPath(".codetaster/ratings.json"),
            base_probability=Probability.fake(),
            working_tree=WorkingTreeState.CLEAN,
        )


type RatingsTemplateError = MissingReviewSettingsError | ChangeReadError


def create_ratings_template(
    request: RatingsTemplateRequest,
    configuration: Configuration,
    committed_changes: CommittedChanges,
) -> Result[RatingsTemplateResult, RatingsTemplateError]:
    """List every file changed since the merge base with the base, to be rated.

    The ratings file itself is left out, as `check` never assesses it.
    """
    review = configuration.review
    if review is None:
        return Err(MissingReviewSettingsError())
    base = request.base_override or review.base_branch
    change = committed_changes.read_committed_change(request.checkout, base)
    if isinstance(change, Err):
        return change
    working_tree = committed_changes.read_working_tree_state(request.checkout)
    if isinstance(working_tree, Err):
        return working_tree
    return Ok(
        RatingsTemplateResult(
            template=RatingsTemplate.of_changes(
                change.value.files.without(review.ratings_path)
            ),
            ratings_path=review.ratings_path,
            base_probability=review.base_probability,
            working_tree=working_tree.value,
        )
    )
