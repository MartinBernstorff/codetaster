"""What `check`, `ratings template` and `ratings validate` all read first."""

from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.errors import (
    MissingReviewSettingsError,
)
from codetaster.domain.domain_model.configuration.review_settings import (
    ReviewSettings,
)
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    CommittedChange,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.ratings import ratings_file_location
from codetaster.domain.secondary_ports.committed_changes import (
    ChangeReadError,
    CommittedChanges,
)


class BranchChange(BaseModel):
    """The change since the merge base with the base, and the settings to review it.

    `change` leaves out the ratings file, which is never reviewed or rated.
    """

    model_config = ConfigDict(frozen=True)

    review: ReviewSettings
    change: CommittedChange
    working_tree: WorkingTreeState
    ratings_location: Location

    @staticmethod
    def fake() -> BranchChange:
        review = ReviewSettings.fake()
        return BranchChange(
            review=review,
            change=CommittedChange.fake(),
            working_tree=WorkingTreeState.CLEAN,
            ratings_location=ratings_file_location(
                CheckoutPath.fake(), review.ratings_path
            ),
        )


type BranchChangeError = MissingReviewSettingsError | ChangeReadError


def read_branch_change(
    checkout: CheckoutPath,
    base_override: RevisionName | None,
    configuration: Configuration,
    committed_changes: CommittedChanges,
) -> Result[BranchChange, BranchChangeError]:
    """The committed change in `checkout`, against `base_override` or the base branch."""
    review = configuration.review
    if review is None:
        return Err(MissingReviewSettingsError())
    base = base_override or review.base_branch
    change = committed_changes.read_committed_change(checkout, base)
    if isinstance(change, Err):
        return change
    working_tree = committed_changes.read_working_tree_state(checkout)
    if isinstance(working_tree, Err):
        return working_tree
    # `checkout` may be a subdirectory; ratings_path is from the repository root.
    root = committed_changes.read_repository_root(checkout)
    if isinstance(root, Err):
        return root
    return Ok(
        BranchChange(
            review=review,
            change=change.value.model_copy(
                update={"files": change.value.files.without(review.ratings_path)}
            ),
            working_tree=working_tree.value,
            ratings_location=ratings_file_location(root.value, review.ratings_path),
        )
    )
