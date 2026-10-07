from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.errors import (
    MissingReviewSettingsError,
)
from codetaster.domain.domain_model.review.changes import RevisionName
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileError,
    ratings_file_location,
)
from codetaster.domain.domain_model.review.sampling import (
    FileAssessments,
    assess_file_change,
)
from codetaster.domain.secondary_ports.committed_changes import (
    ChangeReadError,
    CommittedChanges,
)
from codetaster.domain.secondary_ports.ratings_file_store import RatingsFileStore


class CheckRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkout: CheckoutPath
    base_override: RevisionName | None

    @staticmethod
    def fake() -> CheckRequest:
        return CheckRequest(checkout=CheckoutPath.fake(), base_override=None)


type CheckError = MissingReviewSettingsError | ChangeReadError | RatingsFileError


def check_committed_changes(
    request: CheckRequest,
    configuration: Configuration,
    committed_changes: CommittedChanges,
    ratings_files: RatingsFileStore,
) -> Result[CheckResult, CheckError]:
    """Decide which files changed since the merge base with the base need review.

    A file's AI rating applies if it matches the file's change. Without a ratings
    file every file is unrated. The ratings file itself is never assessed.
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
    ratings = ratings_files.read_ratings(
        ratings_file_location(request.checkout, review.ratings_path)
    )
    if isinstance(ratings, Err):
        return ratings
    ratings_file = ratings.value or RatingsFile(ratings=())
    return Ok(
        CheckResult(
            base=change.value.base,
            merge_base=change.value.merge_base,
            head=change.value.head,
            assessments=FileAssessments(
                tuple(
                    assess_file_change(
                        file, review.base_probability, ratings_file.rating_for(file)
                    )
                    for file in change.value.files.without(review.ratings_path).root
                )
            ),
            working_tree=working_tree.value,
        )
    )
