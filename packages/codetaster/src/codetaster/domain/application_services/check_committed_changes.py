from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.review.changes import RevisionName
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.ratings import RatingsFile
from codetaster.domain.domain_model.review.ratings_validation import (
    InvalidRatingsFile,
)
from codetaster.domain.domain_model.review.sampling import (
    assess_file_changes,
)
from codetaster.domain.domain_model.review.top_rated import TopRatedPercentage
from codetaster.domain.domain_services.branch_change import (
    BranchChangeError,
    read_branch_change,
)
from codetaster.domain.secondary_ports.committed_changes import CommittedChanges
from codetaster.domain.secondary_ports.ratings_file_store import RatingsFileStore


class CheckRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkout: CheckoutPath
    base_override: RevisionName | None
    top_rated_override: TopRatedPercentage | None

    @staticmethod
    def fake() -> CheckRequest:
        return CheckRequest(
            checkout=CheckoutPath.fake(), base_override=None, top_rated_override=None
        )


def check_committed_changes(
    request: CheckRequest,
    configuration: Configuration,
    committed_changes: CommittedChanges,
    ratings_files: RatingsFileStore,
) -> Result[CheckResult, BranchChangeError]:
    """Decide which files changed since the merge base with the base need review.

    A file's AI rating applies if it matches the file's change. Without a ratings
    file every file is unrated, and so with an invalid one, which is reported. The
    ratings file itself is never assessed. `top_rated_override` replaces
    `[review] top_rated_percentage`.
    """
    branch = read_branch_change(
        request.checkout, request.base_override, configuration, committed_changes
    )
    if isinstance(branch, Err):
        return branch
    change = branch.value.change
    ratings = ratings_files.read_ratings(branch.value.ratings_location)
    ratings_file = RatingsFile(ratings=())
    ratings_problem = None
    if isinstance(ratings, Err):
        ratings_problem = InvalidRatingsFile(
            location=ratings.error.location, reason=ratings.error.reason
        )
    elif ratings.value is not None:
        ratings_file = ratings.value
    review = branch.value.review
    top_rated = request.top_rated_override or review.top_rated_percentage
    return Ok(
        CheckResult(
            base=change.base,
            merge_base=change.merge_base,
            head=change.head,
            top_rated_percentage=top_rated,
            assessments=assess_file_changes(
                change.files, review.base_probability, ratings_file, top_rated
            ),
            working_tree=branch.value.working_tree,
            ratings_problem=ratings_problem,
        )
    )
