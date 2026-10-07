from safe_result import Err, Ok

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.errors import (
    MissingReviewSettingsError,
)
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    RepositoryPath,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.ratings import ratings_file_location
from codetaster.domain.domain_services.branch_change import (
    BranchChange,
    read_branch_change,
)

# Domain tests use the fakes from infrastructure, which tach otherwise forbids.
from codetaster.infrastructure.committed_changes.fake_committed_changes import (
    FakeCommittedChanges,
)


def history_with_feature_branch(
    base: RevisionName, *feature_files: RepositoryPath
) -> FakeCommittedChanges:
    """`base` has one commit; the checked-out `feature` branch adds `feature_files`."""
    history = FakeCommittedChanges(base)
    _ = history.commit({RepositoryPath("README.md"): BlobSha.fake()})
    history.create_branch(RevisionName("feature"))
    _ = history.commit({path: BlobSha.fake() for path in feature_files})
    return history


def branch_change(
    configuration: Configuration,
    history: FakeCommittedChanges,
    base_override: RevisionName | None = None,
) -> BranchChange:
    match read_branch_change(
        CheckoutPath.fake(), base_override, configuration, history
    ):
        case Ok(result):
            return result
        case Err(error):
            raise error


def test_leaves_out_the_ratings_file() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    other = RepositoryPath("other.py")
    history = history_with_feature_branch(
        configuration.review.base_branch, configuration.review.ratings_path, other
    )

    result = branch_change(configuration, history)

    assert [file.path() for file in result.change.files.root] == [other]


def test_base_override_replaces_the_configured_base_branch() -> None:
    override = RevisionName("release")
    history = history_with_feature_branch(override, RepositoryPath.fake())

    result = branch_change(Configuration.fake(), history, override)

    assert result.change.base == override


def test_reports_the_working_tree_and_ratings_location() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(configuration.review.base_branch)
    history.working_tree = WorkingTreeState.DIRTY
    location = ratings_file_location(
        CheckoutPath.fake(), configuration.review.ratings_path
    )

    result = branch_change(configuration, history)

    assert result.working_tree is WorkingTreeState.DIRTY
    assert result.ratings_location == location


def test_the_ratings_file_is_found_from_the_repository_root() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(configuration.review.base_branch)
    subdirectory = CheckoutPath(history.repository_root.root / "src")
    location = ratings_file_location(
        history.repository_root, configuration.review.ratings_path
    )

    result = read_branch_change(subdirectory, None, configuration, history)

    match result:
        case Ok(branch):
            assert branch.ratings_location == location
        case Err(error):
            raise error


def test_missing_review_settings_is_an_error() -> None:
    configuration = Configuration.fake().model_copy(update={"review": None})

    result = read_branch_change(
        CheckoutPath.fake(),
        None,
        configuration,
        FakeCommittedChanges(RevisionName.fake()),
    )

    match result:
        case Err(MissingReviewSettingsError()):
            pass
        case _:
            raise AssertionError(result)
