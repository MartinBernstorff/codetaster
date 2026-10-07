from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.ratings_validation import (
    InvalidRatingsFile,
    MissingRatingsFile,
    RatingProblems,
    find_rating_problems,
)
from codetaster.domain.domain_services.branch_change import (
    BranchChangeError,
    read_branch_change,
)
from codetaster.domain.secondary_ports.committed_changes import CommittedChanges
from codetaster.domain.secondary_ports.ratings_file_store import RatingsFileStore


class RatingsValidationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkout: CheckoutPath
    base_override: RevisionName | None

    @staticmethod
    def fake() -> RatingsValidationRequest:
        return RatingsValidationRequest(
            checkout=CheckoutPath.fake(), base_override=None
        )


class RatingsValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    problems: RatingProblems
    location: Location
    working_tree: WorkingTreeState

    @staticmethod
    def fake() -> RatingsValidationResult:
        return RatingsValidationResult(
            problems=RatingProblems.fake(),
            location=Location.fake(),
            working_tree=WorkingTreeState.CLEAN,
        )


def validate_ratings_file(
    request: RatingsValidationRequest,
    configuration: Configuration,
    committed_changes: CommittedChanges,
    ratings_files: RatingsFileStore,
) -> Result[RatingsValidationResult, BranchChangeError]:
    """Check the ratings file rates every file changed since the merge base, once.

    A missing or invalid ratings file is a problem, not an error. The ratings file
    itself needs no rating.
    """
    branch = read_branch_change(
        request.checkout, request.base_override, configuration, committed_changes
    )
    if isinstance(branch, Err):
        return branch
    location = branch.value.ratings_location
    ratings = ratings_files.read_ratings(location)
    if isinstance(ratings, Err):
        problems = RatingProblems(
            (InvalidRatingsFile(location=location, reason=ratings.error.reason),)
        )
    elif ratings.value is None:
        problems = RatingProblems((MissingRatingsFile(location=location),))
    else:
        problems = find_rating_problems(branch.value.change.files, ratings.value)
    return Ok(
        RatingsValidationResult(
            problems=problems, location=location, working_tree=branch.value.working_tree
        )
    )
