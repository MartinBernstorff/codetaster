from safe_result import Err, Ok

from codetaster.domain.application_services.create_ratings_template import (
    RatingsTemplateRequest,
    RatingsTemplateResult,
    create_ratings_template,
)
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
from codetaster.domain.domain_model.review.errors import UnknownRevisionError
from codetaster.domain.domain_model.review.ratings import RatingTarget

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


def created_template(
    configuration: Configuration,
    history: FakeCommittedChanges,
    request: RatingsTemplateRequest | None = None,
) -> RatingsTemplateResult:
    match create_ratings_template(
        request or RatingsTemplateRequest.fake(), configuration, history
    ):
        case Ok(result):
            return result
        case Err(error):
            raise error


def test_lists_every_changed_file_at_head() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    paths = [RepositoryPath("one.py"), RepositoryPath("two.py")]
    history = history_with_feature_branch(configuration.review.base_branch, *paths)
    head = history.commits[history.branches[history.current_branch]]

    result = created_template(configuration, history)

    assert [entry.target() for entry in result.template.ratings] == [
        RatingTarget(path=path, blob=head.tree[path]) for path in paths
    ]


def test_a_deleted_file_has_no_blob() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    deleted = RepositoryPath("README.md")
    history = history_with_feature_branch(configuration.review.base_branch)
    _ = history.commit({deleted: None})

    result = created_template(configuration, history)

    assert [entry.target() for entry in result.template.ratings] == [
        RatingTarget(path=deleted, blob=None)
    ]


def test_never_lists_the_ratings_file() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    other = RepositoryPath("other.py")
    history = history_with_feature_branch(
        configuration.review.base_branch, configuration.review.ratings_path, other
    )

    result = created_template(configuration, history)

    assert [entry.path for entry in result.template.ratings] == [other]


def test_reports_the_review_settings_the_agent_needs() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, RepositoryPath.fake()
    )

    result = created_template(configuration, history)

    assert result.ratings_path == configuration.review.ratings_path
    assert result.base_probability == configuration.review.base_probability


def test_base_override_replaces_the_configured_base_branch() -> None:
    override = RevisionName("release")
    path = RepositoryPath.fake()
    history = history_with_feature_branch(override, path)
    request = RatingsTemplateRequest.fake().model_copy(
        update={"base_override": override}
    )

    result = created_template(Configuration.fake(), history, request)

    assert [entry.path for entry in result.template.ratings] == [path]


def test_reports_a_dirty_working_tree() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, RepositoryPath.fake()
    )
    history.working_tree = WorkingTreeState.DIRTY

    result = created_template(configuration, history)

    assert result.working_tree is WorkingTreeState.DIRTY


def test_missing_review_settings_is_an_error() -> None:
    configuration = Configuration.fake().model_copy(update={"review": None})

    result = create_ratings_template(
        RatingsTemplateRequest.fake(),
        configuration,
        FakeCommittedChanges(RevisionName.fake()),
    )

    match result:
        case Err(MissingReviewSettingsError()):
            pass
        case _:
            raise AssertionError(result)


def test_unknown_base_is_an_error() -> None:
    unknown = RevisionName("no-such-branch")
    request = RatingsTemplateRequest.fake().model_copy(
        update={"base_override": unknown}
    )
    history = history_with_feature_branch(RevisionName.fake(), RepositoryPath.fake())

    result = create_ratings_template(request, Configuration.fake(), history)

    match result:
        case Err(UnknownRevisionError() as error):
            assert error.revision == unknown
        case _:
            raise AssertionError(result)
