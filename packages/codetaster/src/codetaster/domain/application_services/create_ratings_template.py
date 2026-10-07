from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.domain_model.review.top_rated import TopRatedPercentage
from codetaster.domain.domain_services.branch_change import (
    BranchChangeError,
    read_branch_change,
)
from codetaster.domain.secondary_ports.committed_changes import CommittedChanges


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
    ratings_location: Location
    base_probability: Probability
    top_rated_percentage: TopRatedPercentage
    working_tree: WorkingTreeState

    @staticmethod
    def fake() -> RatingsTemplateResult:
        return RatingsTemplateResult(
            template=RatingsTemplate.fake(),
            ratings_location=Location.fake(),
            base_probability=Probability.fake(),
            top_rated_percentage=TopRatedPercentage.fake(),
            working_tree=WorkingTreeState.CLEAN,
        )


def create_ratings_template(
    request: RatingsTemplateRequest,
    configuration: Configuration,
    committed_changes: CommittedChanges,
) -> Result[RatingsTemplateResult, BranchChangeError]:
    """List every file changed since the merge base with the base, to be rated.

    The ratings file itself is left out, as `check` never assesses it.
    """
    branch = read_branch_change(
        request.checkout, request.base_override, configuration, committed_changes
    )
    if isinstance(branch, Err):
        return branch
    return Ok(
        RatingsTemplateResult(
            template=RatingsTemplate.of_changes(branch.value.change.files),
            ratings_location=branch.value.ratings_location,
            base_probability=branch.value.review.base_probability,
            top_rated_percentage=branch.value.review.top_rated_percentage,
            working_tree=branch.value.working_tree,
        )
    )
