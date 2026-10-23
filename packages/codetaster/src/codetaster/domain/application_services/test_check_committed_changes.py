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
from codetaster.domain.domain_model.review.adaptive_sampling import (
    BaseProbabilityWeight,
    SamplingEvidence,
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
from codetaster.domain.domain_model.review.needs_review_threshold import (
    NeedsReviewThreshold,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    RatingsFileContent,
    ratings_file_location,
)
from codetaster.domain.domain_model.review.sampling import Verdict
from codetaster.domain.domain_model.review.test_strategies import ratings_file_of

# Domain tests use the fakes from infrastructure, which tach otherwise forbids.
from codetaster.infrastructure.committed_changes.fake_committed_changes import (
    FakeCommittedChanges,
)
from codetaster.infrastructure.ratings_file_store.in_memory import (
    InMemoryRatingsFileStore,
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


def configuration_with(
    base_probability: Probability,
    threshold: NeedsReviewThreshold | None = None,
) -> Configuration:
    """All rated files need review unless `threshold` says otherwise."""
    review = ReviewSettings.fake().model_copy(
        update={
            "base_probability": base_probability,
            "needs_review_threshold": threshold or NeedsReviewThreshold(0),
        }
    )
    return Configuration.fake().model_copy(update={"review": review})


def checked_result(
    configuration: Configuration,
    history: FakeCommittedChanges,
    request: CheckRequest | None = None,
    ratings_files: InMemoryRatingsFileStore | None = None,
) -> CheckResult:
    match check_committed_changes(
        request or CheckRequest.fake(),
        configuration,
        history,
        ratings_files or InMemoryRatingsFileStore({}),
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

    result = checked_result(configuration, history)

    assert [assessment.change.path() for assessment in result.assessments.root] == (
        paths
    )
    assert {
        assessment.change.change_type() for assessment in result.assessments.root
    } == {ChangeType.ADDED}
    assert {assessment.base_probability for assessment in result.assessments.root} == {
        configuration.review.base_probability
    }


def test_the_evidence_and_configured_weight_decide_the_sampling() -> None:
    weight = BaseProbabilityWeight(4)
    review = ReviewSettings.fake().model_copy(
        update={"base_probability": Probability(0.3), "base_probability_weight": weight}
    )
    configuration = Configuration.fake().model_copy(update={"review": review})
    history = history_with_feature_branch(review.base_branch, RepositoryPath.fake())
    evidence = SamplingEvidence.fake()
    request = CheckRequest.fake().model_copy(update={"evidence": evidence})

    result = checked_result(configuration, history, request)

    assert result.sampling.weight == weight
    assert result.sampling.evidence == evidence
    assert {
        assessment.sampling_probability for assessment in result.assessments.root
    } == {result.sampling.adjusted(review.base_probability)}


def test_reports_base_merge_base_and_head() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    base = configuration.review.base_branch
    history = history_with_feature_branch(base, RepositoryPath.fake())
    merge_base = history.branches[base]
    head = history.branches[history.current_branch]

    result = checked_result(configuration, history)

    assert result.base == base
    assert result.merge_base == merge_base
    assert result.head == head


def test_base_override_replaces_the_configured_base_branch() -> None:
    override = RevisionName("release")
    history = history_with_feature_branch(override, RepositoryPath.fake())
    request = CheckRequest.fake().model_copy(update={"base_override": override})

    result = checked_result(Configuration.fake(), history, request)

    assert result.base == override


def test_missing_review_settings_is_an_error() -> None:
    configuration = Configuration.fake().model_copy(update={"review": None})

    result = check_committed_changes(
        CheckRequest.fake(),
        configuration,
        FakeCommittedChanges(RevisionName.fake()),
        InMemoryRatingsFileStore({}),
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

    result = check_committed_changes(
        request, Configuration.fake(), history, InMemoryRatingsFileStore({})
    )

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

    result = checked_result(configuration, history)

    assert result.working_tree is WorkingTreeState.DIRTY


def ratings_at(
    configuration: Configuration, *ratings: FileRating
) -> InMemoryRatingsFileStore:
    assert configuration.review is not None
    store = InMemoryRatingsFileStore({})
    store.write_ratings(
        ratings_file_location(
            CheckRequest.fake().checkout, configuration.review.ratings_path
        ),
        ratings_file_of(*ratings),
    )
    return store


def certain_rating_at_head(
    history: FakeCommittedChanges, path: RepositoryPath
) -> FileRating:
    """A rating of 1 for `path` as it is at the head of the current branch."""
    head = history.commits[history.branches[history.current_branch]]
    return FileRating.fake().model_copy(
        update={"path": path, "blob": head.tree[path], "probability": Probability(1)}
    )


def test_a_matching_rating_applies() -> None:
    configuration = configuration_with(Probability(0))
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)
    rating = certain_rating_at_head(history, path)

    result = checked_result(
        configuration, history, ratings_files=ratings_at(configuration, rating)
    )

    [assessment] = result.assessments.root
    assert assessment.rating == rating
    assert assessment.verdict is Verdict.NEEDS_REVIEW


def test_a_stale_rating_is_ignored() -> None:
    configuration = configuration_with(Probability(0))
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)
    rating = certain_rating_at_head(history, path)
    _ = history.commit({path: BlobSha("e" * 40)})

    result = checked_result(
        configuration, history, ratings_files=ratings_at(configuration, rating)
    )

    [assessment] = result.assessments.root
    assert assessment.rating is None
    assert assessment.verdict is Verdict.NO_REVIEW


def test_without_a_ratings_file_every_file_is_unrated() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    paths = [RepositoryPath("one.py"), RepositoryPath("two.py")]
    history = history_with_feature_branch(configuration.review.base_branch, *paths)

    result = checked_result(configuration, history)

    assert {assessment.rating for assessment in result.assessments.root} == {None}


def test_the_ratings_file_is_never_assessed() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    other = RepositoryPath("other.py")
    history = history_with_feature_branch(
        configuration.review.base_branch, configuration.review.ratings_path, other
    )

    result = checked_result(configuration, history)

    assert [assessment.change.path() for assessment in result.assessments.root] == [
        other
    ]


def test_an_invalid_ratings_file_leaves_every_file_unrated_and_is_reported() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, RepositoryPath.fake()
    )
    location = ratings_file_location(
        CheckRequest.fake().checkout, configuration.review.ratings_path
    )
    store = InMemoryRatingsFileStore({location: RatingsFileContent("not json")})

    result = checked_result(configuration, history, ratings_files=store)

    assert {assessment.rating for assessment in result.assessments.root} == {None}
    assert result.ratings_problem is not None
    assert result.ratings_problem.location == location


def test_a_valid_ratings_file_is_no_problem() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, RepositoryPath.fake()
    )

    result = checked_result(
        configuration, history, ratings_files=ratings_at(configuration)
    )

    assert result.ratings_problem is None


def rating_below_one_at_head(
    history: FakeCommittedChanges, path: RepositoryPath
) -> FileRating:
    return certain_rating_at_head(history, path).model_copy(
        update={"probability": Probability(0.9)}
    )


def test_the_configured_needs_review_threshold_applies() -> None:
    configuration = configuration_with(Probability(0), NeedsReviewThreshold(1))
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)
    rating = rating_below_one_at_head(history, path)

    result = checked_result(
        configuration, history, ratings_files=ratings_at(configuration, rating)
    )

    [assessment] = result.assessments.root
    assert result.needs_review_threshold == configuration.review.needs_review_threshold
    assert assessment.verdict is Verdict.NO_REVIEW


def test_threshold_override_replaces_the_configured_threshold() -> None:
    configuration = configuration_with(Probability(0), NeedsReviewThreshold(1))
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)
    rating = rating_below_one_at_head(history, path)
    override = NeedsReviewThreshold(0.9)
    request = CheckRequest.fake().model_copy(update={"threshold_override": override})

    result = checked_result(
        configuration, history, request, ratings_at(configuration, rating)
    )

    [assessment] = result.assessments.root
    assert result.needs_review_threshold == override
    assert assessment.verdict is Verdict.NEEDS_REVIEW
