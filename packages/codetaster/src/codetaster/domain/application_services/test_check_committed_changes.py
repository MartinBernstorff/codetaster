from safe_result import Err, Ok

from codetaster.domain.application_services.check_committed_changes import (
    CheckRequest,
    check_committed_changes,
)
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.errors import (
    MissingReviewSettingsError,
)
from codetaster.domain.domain_model.configuration.review_settings import (
    ReviewSettings,
)
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    ChangeType,
    RepositoryPath,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.errors import UnknownRevisionError
from codetaster.domain.domain_model.review.sampling import Probability, Verdict

# Domain tests use the fakes from infrastructure, which tach otherwise forbids.
from codetaster.infrastructure.committed_changes.fake_committed_changes import (
    FakeCommittedChanges,
)

FEATURE = RevisionName("feature")


def history_with_feature_branch(
    base: RevisionName, *feature_files: RepositoryPath
) -> FakeCommittedChanges:
    """`base` has one commit; the checked-out feature branch adds `feature_files`."""
    history = FakeCommittedChanges()
    history.switch_to(base)
    _ = history.commit({RepositoryPath("README.md"): BlobSha.fake()})
    history.create_branch(FEATURE)
    _ = history.commit({path: BlobSha.fake() for path in feature_files})
    return history


def configuration_with(base_probability: Probability) -> Configuration:
    review = ReviewSettings.fake().model_copy(
        update={"base_probability": base_probability}
    )
    return Configuration.fake().model_copy(update={"review": review})


def checked(
    configuration: Configuration,
    history: FakeCommittedChanges,
    request: CheckRequest | None = None,
) -> CheckResult:
    match check_committed_changes(
        request or CheckRequest.fake(), configuration, history
    ):
        case Ok(result):
            return result
        case Err(error):
            raise error


def test_every_changed_file_is_assessed_at_the_base_probability() -> None:
    configuration = configuration_with(Probability(0.3))
    assert configuration.review is not None
    paths = [RepositoryPath("one.py"), RepositoryPath("two.py")]
    history = history_with_feature_branch(configuration.review.base_branch, *paths)

    result = checked(configuration, history)

    assert [assessment.change.path() for assessment in result.assessments.root] == (
        paths
    )
    assert {
        assessment.change.change_type() for assessment in result.assessments.root
    } == {ChangeType.ADDED}
    assert {assessment.probability for assessment in result.assessments.root} == {
        configuration.review.base_probability
    }


def test_files_are_categorised_by_their_draw() -> None:
    always = configuration_with(Probability(1))
    never = configuration_with(Probability(0))
    assert always.review is not None
    history = history_with_feature_branch(
        always.review.base_branch, RepositoryPath.fake()
    )

    assert checked(always, history).verdict() is Verdict.NEEDS_REVIEW
    assert checked(never, history).verdict() is Verdict.NO_REVIEW


def test_reports_base_merge_base_and_head() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    base = configuration.review.base_branch
    history = history_with_feature_branch(base, RepositoryPath.fake())
    merge_base = history.branches[base]
    head = history.branches[FEATURE]

    result = checked(configuration, history)

    assert result.base == base
    assert result.merge_base == merge_base
    assert result.head == head


def test_base_override_replaces_the_configured_base_branch() -> None:
    override = RevisionName("release")
    history = history_with_feature_branch(override, RepositoryPath.fake())
    request = CheckRequest.fake().model_copy(update={"base_override": override})

    result = checked(Configuration.fake(), history, request)

    assert result.base == override


def test_missing_review_settings_is_an_error() -> None:
    configuration = Configuration.fake().model_copy(update={"review": None})

    result = check_committed_changes(
        CheckRequest.fake(), configuration, FakeCommittedChanges()
    )

    match result:
        case Err(MissingReviewSettingsError()):
            pass
        case _:
            raise AssertionError(result)


def test_unknown_base_is_an_error() -> None:
    unknown = RevisionName("no-such-branch")
    request = CheckRequest.fake().model_copy(update={"base_override": unknown})
    history = history_with_feature_branch(RevisionName.fake(), RepositoryPath.fake())

    result = check_committed_changes(request, Configuration.fake(), history)

    match result:
        case Err(UnknownRevisionError() as error):
            assert error.revision == unknown
        case _:
            raise AssertionError(result)


def test_reports_a_dirty_working_tree() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, RepositoryPath.fake()
    )
    history.working_tree = WorkingTreeState.DIRTY

    result = checked(configuration, history)

    assert result.working_tree is WorkingTreeState.DIRTY
