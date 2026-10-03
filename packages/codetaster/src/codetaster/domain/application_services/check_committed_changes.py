from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.errors import (
    MissingReviewSettingsError,
)
from codetaster.domain.domain_model.review.changes import RevisionName
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.sampling import (
    FileAssessments,
    assess_file_change,
)
from codetaster.domain.secondary_ports.committed_changes import (
    ChangeReadError,
    CommittedChanges,
)


class CheckRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkout: CheckoutPath
    base_override: RevisionName | None

    @staticmethod
    def fake() -> CheckRequest:
        return CheckRequest(checkout=CheckoutPath.fake(), base_override=None)


type CheckError = MissingReviewSettingsError | ChangeReadError


def check_committed_changes(
    request: CheckRequest,
    configuration: Configuration,
    history: CommittedChanges,
) -> Result[CheckResult, CheckError]:
    """Sample which files changed since the merge base with the base need review."""
    review = configuration.review
    if review is None:
        return Err(MissingReviewSettingsError())
    base = request.base_override or review.base_branch
    change = history.read_committed_change(request.checkout, base)
    if isinstance(change, Err):
        return change
    working_tree = history.read_working_tree_state(request.checkout)
    if isinstance(working_tree, Err):
        return working_tree
    return Ok(
        CheckResult(
            base=change.value.base,
            merge_base=change.value.merge_base,
            head=change.value.head,
            assessments=FileAssessments(
                tuple(
                    assess_file_change(file, review.base_probability)
                    for file in change.value.files.root
                )
            ),
            working_tree=working_tree.value,
        )
    )
