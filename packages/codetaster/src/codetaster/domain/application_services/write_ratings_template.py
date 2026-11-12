from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.filesystem import ExistingFilePolicy, Location
from codetaster.domain.domain_model.review.changes import (
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.ratings import (
    RatingsFileExistsError,
    RatingsFileWriteError,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.domain_services.branch_change import (
    BranchChangeError,
    read_branch_change,
)
from codetaster.domain.secondary_ports.committed_changes import CommittedChanges
from codetaster.domain.secondary_ports.ratings_file_store import RatingsFileStore


class RatingsTemplateWriteRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkout: CheckoutPath
    base_override: RevisionName | None
    existing_file: ExistingFilePolicy

    @staticmethod
    def fake() -> RatingsTemplateWriteRequest:
        return RatingsTemplateWriteRequest(
            checkout=CheckoutPath.fake(),
            base_override=None,
            existing_file=ExistingFilePolicy.REFUSE,
        )


class RatingsTemplateWriteResult(BaseModel):
    """Where the template was written, and whether uncommitted changes were left
    out of it."""

    model_config = ConfigDict(frozen=True)

    location: Location
    working_tree: WorkingTreeState

    @staticmethod
    def fake() -> RatingsTemplateWriteResult:
        return RatingsTemplateWriteResult(
            location=Location.fake(), working_tree=WorkingTreeState.CLEAN
        )


type RatingsTemplateWriteError = (
    BranchChangeError | RatingsFileExistsError | RatingsFileWriteError
)


def write_ratings_template(
    request: RatingsTemplateWriteRequest,
    configuration: Configuration,
    committed_changes: CommittedChanges,
    ratings_files: RatingsFileStore,
) -> Result[RatingsTemplateWriteResult, RatingsTemplateWriteError]:
    """Write a template listing every file changed since the merge base with the
    base to `[review] ratings_path`, for an agent to fill in.

    Refuses to replace an existing ratings file unless asked to, so ratings
    already written are not lost. The ratings file itself is left out of the
    template, as `check` never assesses it.
    """
    branch = read_branch_change(
        request.checkout, request.base_override, configuration, committed_changes
    )
    if isinstance(branch, Err):
        return branch
    location = branch.value.ratings_location
    if request.existing_file is ExistingFilePolicy.REFUSE and ratings_files.exists(
        location
    ):
        return Err(RatingsFileExistsError(location))
    written = ratings_files.write_template(
        location, RatingsTemplate.of_changes(branch.value.change.files)
    )
    if isinstance(written, Err):
        return written
    return Ok(
        RatingsTemplateWriteResult(
            location=location, working_tree=branch.value.working_tree
        )
    )
