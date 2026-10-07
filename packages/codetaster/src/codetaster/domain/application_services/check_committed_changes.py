from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.review.changes import RevisionName
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileError,
)
from codetaster.domain.domain_model.review.sampling import (
    FileAssessments,
    assess_file_change,
)
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

    @staticmethod
    def fake() -> CheckRequest:
        return CheckRequest(checkout=CheckoutPath.fake(), base_override=None)


type CheckError = BranchChangeError | RatingsFileError


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
    branch = read_branch_change(
        request.checkout, request.base_override, configuration, committed_changes
    )
    if isinstance(branch, Err):
        return branch
    change = branch.value.change
    ratings = ratings_files.read_ratings(branch.value.ratings_location)
    if isinstance(ratings, Err):
        return ratings
    ratings_file = ratings.value or RatingsFile(ratings=())
    base_probability = branch.value.review.base_probability
    return Ok(
        CheckResult(
            base=change.base,
            merge_base=change.merge_base,
            head=change.head,
            assessments=FileAssessments(
                tuple(
                    assess_file_change(
                        file, base_probability, ratings_file.rating_for(file)
                    )
                    for file in change.files.root
                )
            ),
            working_tree=branch.value.working_tree,
        )
    )
