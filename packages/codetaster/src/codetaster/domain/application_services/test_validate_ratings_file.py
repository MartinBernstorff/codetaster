from safe_result import Err, Ok

from codetaster.domain.application_services.validate_ratings_file import (
    RatingsValidationRequest,
    RatingsValidationResult,
    validate_ratings_file,
)
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.errors import (
    MissingReviewSettingsError,
)
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    LineCount,
    RepositoryPath,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.errors import UnknownRevisionError
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    LineAnnotation,
    LineNumber,
    RatingsFileContent,
    RatingTarget,
    ratings_file_location,
)
from codetaster.domain.domain_model.review.ratings_validation import (
    AnnotationLineOutOfRange,
    AnnotationOnUnreadableFile,
    InvalidRatingsFile,
    MissingRatingsFile,
    RatingProblems,
    UnratedFile,
)
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


def head_target(history: FakeCommittedChanges, path: RepositoryPath) -> RatingTarget:
    head = history.commits[history.branches[history.current_branch]]
    return RatingTarget(path=path, blob=head.tree[path])


def rating_for(target: RatingTarget) -> FileRating:
    return FileRating.fake().model_copy(
        update={"path": target.path, "blob": target.blob}
    )


def ratings_store(
    configuration: Configuration, *ratings: FileRating
) -> InMemoryRatingsFileStore:
    assert configuration.review is not None
    store = InMemoryRatingsFileStore({})
    store.write_ratings(
        ratings_file_location(
            RatingsValidationRequest.fake().checkout, configuration.review.ratings_path
        ),
        ratings_file_of(*ratings),
    )
    return store


def validated(
    configuration: Configuration,
    history: FakeCommittedChanges,
    ratings_files: InMemoryRatingsFileStore,
    request: RatingsValidationRequest | None = None,
) -> RatingsValidationResult:
    match validate_ratings_file(
        request or RatingsValidationRequest.fake(),
        configuration,
        history,
        ratings_files,
    ):
        case Ok(result):
            return result
        case Err(error):
            raise error


def test_a_rating_for_every_changed_file_has_no_problems() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)
    store = ratings_store(configuration, rating_for(head_target(history, path)))

    result = validated(configuration, history, store)

    assert result.problems == RatingProblems(())


def test_reports_an_annotation_past_the_last_line() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)
    target = head_target(history, path)
    assert target.blob is not None
    line_count = LineCount(3)
    history.line_counts[target.blob] = line_count
    annotation = LineAnnotation.fake().model_copy(update={"line": LineNumber(4)})
    rating = rating_for(target).model_copy(update={"annotations": (annotation,)})

    result = validated(configuration, history, ratings_store(configuration, rating))

    assert result.problems == RatingProblems(
        (
            AnnotationLineOutOfRange(
                target=target, annotation=annotation, line_count=line_count
            ),
        )
    )


def test_an_unreadable_annotated_file_is_a_problem_not_an_error() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    unreadable = RepositoryPath("submodule")
    readable = RepositoryPath.fake()
    history = history_with_feature_branch(
        configuration.review.base_branch, unreadable, readable
    )
    unreadable_target = head_target(history, unreadable)
    # Both paths have the fake blob; give the readable one its own.
    readable_blob = BlobSha("c" * 40)
    _ = history.commit({readable: readable_blob})
    line_count = LineCount(3)
    history.line_counts[readable_blob] = line_count
    readable_target = head_target(history, readable)
    annotation = LineAnnotation.fake().model_copy(update={"line": LineNumber(4)})
    store = ratings_store(
        configuration,
        rating_for(unreadable_target).model_copy(update={"annotations": (annotation,)}),
        rating_for(readable_target).model_copy(update={"annotations": (annotation,)}),
    )

    result = validated(configuration, history, store)

    assert result.problems == RatingProblems(
        (
            AnnotationOnUnreadableFile(target=unreadable_target, annotation=annotation),
            AnnotationLineOutOfRange(
                target=readable_target, annotation=annotation, line_count=line_count
            ),
        )
    )


def test_reports_an_unrated_changed_file() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    path = RepositoryPath.fake()
    history = history_with_feature_branch(configuration.review.base_branch, path)

    result = validated(configuration, history, ratings_store(configuration))

    assert result.problems == RatingProblems(
        (UnratedFile(target=head_target(history, path)),)
    )


def test_the_ratings_file_need_not_be_rated() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, configuration.review.ratings_path
    )

    result = validated(configuration, history, ratings_store(configuration))

    assert result.problems == RatingProblems(())


def test_a_missing_ratings_file_is_a_problem() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, RepositoryPath.fake()
    )
    location = ratings_file_location(
        RatingsValidationRequest.fake().checkout, configuration.review.ratings_path
    )

    result = validated(configuration, history, InMemoryRatingsFileStore({}))

    assert result.problems == RatingProblems((MissingRatingsFile(location=location),))


def test_an_invalid_ratings_file_is_a_problem() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(
        configuration.review.base_branch, RepositoryPath.fake()
    )
    location = ratings_file_location(
        RatingsValidationRequest.fake().checkout, configuration.review.ratings_path
    )
    store = InMemoryRatingsFileStore({location: RatingsFileContent("not json")})

    result = validated(configuration, history, store)

    match result.problems.root:
        case (InvalidRatingsFile(location=reported),):
            assert reported == location
        case _:
            raise AssertionError(result.problems)


def test_base_override_replaces_the_configured_base_branch() -> None:
    override = RevisionName("release")
    configuration = Configuration.fake()
    path = RepositoryPath.fake()
    history = history_with_feature_branch(override, path)
    request = RatingsValidationRequest.fake().model_copy(
        update={"base_override": override}
    )

    result = validated(configuration, history, ratings_store(configuration), request)

    assert result.problems == RatingProblems(
        (UnratedFile(target=head_target(history, path)),)
    )


def test_reports_a_dirty_working_tree() -> None:
    configuration = Configuration.fake()
    assert configuration.review is not None
    history = history_with_feature_branch(configuration.review.base_branch)
    history.working_tree = WorkingTreeState.DIRTY

    result = validated(configuration, history, ratings_store(configuration))

    assert result.working_tree is WorkingTreeState.DIRTY


def test_missing_review_settings_is_an_error() -> None:
    configuration = Configuration.fake().model_copy(update={"review": None})

    result = validate_ratings_file(
        RatingsValidationRequest.fake(),
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
    request = RatingsValidationRequest.fake().model_copy(
        update={"base_override": unknown}
    )
    history = history_with_feature_branch(RevisionName.fake(), RepositoryPath.fake())

    result = validate_ratings_file(
        request, Configuration.fake(), history, InMemoryRatingsFileStore({})
    )

    match result:
        case Err(UnknownRevisionError() as error):
            assert error.revision == unknown
        case _:
            raise AssertionError(result)
