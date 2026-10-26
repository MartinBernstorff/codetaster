import pytest
from hypothesis import given
from hypothesis import strategies as st
from safe_result import Ok

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    BlobLineCounts,
    BlobSha,
    ChangeLineHunks,
    FileChange,
    FileChanges,
    FileVersion,
    LineCount,
    LineHunk,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    AnnotationSide,
    DescribedCategory,
    FileRating,
    LineAnnotation,
    LineNumber,
    RatedHunk,
    RatingCategory,
    RatingTarget,
    parse_ratings_file,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.domain_model.review.ratings_validation import (
    AnnotationLineOutOfRange,
    AnnotationOnMissingSide,
    AnnotationOnUnreadableFile,
    DuplicateCategory,
    DuplicateRating,
    HunkMismatch,
    RatingProblems,
    StaleRating,
    UndeclaredCategory,
    UnknownRating,
    UnratedFile,
    UnusedCategory,
    annotated_blobs,
    find_rating_problems,
)
from codetaster.domain.domain_model.review.test_strategies import (
    file_changes,
    fill_template,
    line_hunks,
    ratings_file_of,
    ratings_of,
)


def added(path: RepositoryPath, blob: BlobSha) -> FileChange:
    return FileChange(before=None, after=FileVersion(path=path, blob=blob))


def rating_for(target: RatingTarget) -> FileRating:
    return FileRating.fake().model_copy(
        update={"path": target.path, "blob": target.blob}
    )


def test_a_rating_for_every_changed_file_has_no_problems() -> None:
    change = FileChange.fake()

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating_for(RatingTarget.of_change(change))),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems(())


def test_a_changed_file_without_a_rating_is_unrated() -> None:
    target = RatingTarget.of_change(FileChange.fake())

    problems = find_rating_problems(
        FileChanges((FileChange.fake(),)),
        ratings_file_of(),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems((UnratedFile(target=target),))


def test_a_rating_for_an_older_blob_is_stale() -> None:
    path = RepositoryPath.fake()
    current_blob = BlobSha("1" * 40)
    current = RatingTarget(path=path, blob=current_blob)
    old = RatingTarget(path=path, blob=BlobSha("2" * 40))

    problems = find_rating_problems(
        FileChanges((added(path, current_blob),)),
        ratings_file_of(rating_for(old)),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems((StaleRating(rating=old, current=current),))


def test_a_rating_for_an_unchanged_file_is_unknown() -> None:
    change = FileChange.fake()
    unknown = RatingTarget(path=RepositoryPath("unchanged.py"), blob=BlobSha.fake())

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(
            rating_for(RatingTarget.of_change(change)), rating_for(unknown)
        ),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems((UnknownRating(rating=unknown),))


def test_two_ratings_for_the_same_file_are_duplicates() -> None:
    change = FileChange.fake()
    target = RatingTarget.of_change(change)

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating_for(target), rating_for(target)),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems((DuplicateRating(target=target),))


@given(st.data(), st.lists(file_changes(), unique_by=lambda change: change.path()))
def test_any_fill_of_the_template_has_no_problems(
    data: st.DataObject, changes: list[FileChange]
) -> None:
    file_changes_ = FileChanges(tuple(changes))
    hunks = ChangeLineHunks(
        {change.path(): data.draw(line_hunks()) for change in changes}
    )
    template = RatingsTemplate.of_changes(file_changes_, hunks)
    filled = fill_template(
        template,
        [
            data.draw(ratings_of(change, hunks.hunks_to_rate(change)))
            for change in changes
        ],
    )
    parsed = parse_ratings_file(filled, Location.fake())
    assert isinstance(parsed, Ok)

    problems = find_rating_problems(
        file_changes_, parsed.value, hunks, BlobLineCounts({})
    )

    assert problems == RatingProblems(())


def test_a_category_that_is_not_described_is_undeclared() -> None:
    change = FileChange.fake()
    rating = rating_for(RatingTarget.of_change(change))
    ratings = ratings_file_of(rating).model_copy(update={"categories": ()})

    problems = find_rating_problems(
        FileChanges((change,)), ratings, ChangeLineHunks({}), BlobLineCounts({})
    )

    assert problems == RatingProblems((UndeclaredCategory(category=rating.category),))


def test_a_described_category_without_files_is_unused() -> None:
    change = FileChange.fake()
    unused = DescribedCategory.fake().model_copy(
        update={"name": RatingCategory("Unused")}
    )
    ratings = ratings_file_of(rating_for(RatingTarget.of_change(change)))
    ratings = ratings.model_copy(update={"categories": (*ratings.categories, unused)})

    problems = find_rating_problems(
        FileChanges((change,)), ratings, ChangeLineHunks({}), BlobLineCounts({})
    )

    assert problems == RatingProblems((UnusedCategory(category=unused.name),))


def test_a_category_described_twice_is_a_duplicate() -> None:
    change = FileChange.fake()
    ratings = ratings_file_of(rating_for(RatingTarget.of_change(change)))
    ratings = ratings.model_copy(update={"categories": ratings.categories * 2})
    [category] = {category.name for category in ratings.categories}

    problems = find_rating_problems(
        FileChanges((change,)), ratings, ChangeLineHunks({}), BlobLineCounts({})
    )

    assert problems == RatingProblems((DuplicateCategory(category=category),))


def modified(path: RepositoryPath, before: BlobSha, after: BlobSha) -> FileChange:
    return FileChange(
        before=FileVersion(path=path, blob=before),
        after=FileVersion(path=path, blob=after),
    )


def annotation_on(side: AnnotationSide, line: LineNumber) -> LineAnnotation:
    return LineAnnotation.fake().model_copy(update={"side": side, "line": line})


def annotated_rating(change: FileChange, *annotations: LineAnnotation) -> FileRating:
    return rating_for(RatingTarget.of_change(change)).model_copy(
        update={"annotations": annotations}
    )


BEFORE_BLOB = BlobSha("b" * 40)
AFTER_BLOB = BlobSha("a" * 40)


def test_annotations_on_existing_lines_have_no_problems() -> None:
    change = modified(RepositoryPath.fake(), BEFORE_BLOB, AFTER_BLOB)
    rating = annotated_rating(
        change,
        annotation_on(AnnotationSide.BEFORE, LineNumber(2)),
        annotation_on(AnnotationSide.AFTER, LineNumber(3)),
    )
    line_counts = BlobLineCounts({BEFORE_BLOB: LineCount(2), AFTER_BLOB: LineCount(3)})

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating),
        ChangeLineHunks({}),
        line_counts,
    )

    assert problems == RatingProblems(())


@pytest.mark.parametrize(
    "side", [AnnotationSide.BEFORE, AnnotationSide.AFTER], ids=["before", "after"]
)
def test_an_annotation_past_the_last_line_of_its_side_is_out_of_range(
    side: AnnotationSide,
) -> None:
    change = modified(RepositoryPath.fake(), BEFORE_BLOB, AFTER_BLOB)
    line_count = LineCount(2)
    annotation = annotation_on(side, LineNumber(3))
    rating = annotated_rating(change, annotation)
    # Only the annotated side is too short.
    longer = LineCount(10)
    line_counts = BlobLineCounts(
        {
            BEFORE_BLOB: line_count if side is AnnotationSide.BEFORE else longer,
            AFTER_BLOB: line_count if side is AnnotationSide.AFTER else longer,
        }
    )

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating),
        ChangeLineHunks({}),
        line_counts,
    )

    assert problems == RatingProblems(
        (
            AnnotationLineOutOfRange(
                target=rating.target(), annotation=annotation, line_count=line_count
            ),
        )
    )


def test_a_before_annotation_on_an_added_file_has_no_side() -> None:
    change = added(RepositoryPath.fake(), AFTER_BLOB)
    annotation = annotation_on(AnnotationSide.BEFORE, LineNumber.fake())
    rating = annotated_rating(change, annotation)

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating),
        ChangeLineHunks({}),
        BlobLineCounts({AFTER_BLOB: LineCount(10)}),
    )

    assert problems == RatingProblems(
        (AnnotationOnMissingSide(target=rating.target(), annotation=annotation),)
    )


def test_an_after_annotation_on_a_deleted_file_has_no_side() -> None:
    change = FileChange(
        before=FileVersion(path=RepositoryPath.fake(), blob=BEFORE_BLOB), after=None
    )
    annotation = annotation_on(AnnotationSide.AFTER, LineNumber.fake())
    rating = annotated_rating(change, annotation)

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating),
        ChangeLineHunks({}),
        BlobLineCounts({BEFORE_BLOB: LineCount(10)}),
    )

    assert problems == RatingProblems(
        (AnnotationOnMissingSide(target=rating.target(), annotation=annotation),)
    )


def test_annotations_on_an_unchanged_file_are_reported_only_as_the_unknown_rating() -> (
    None
):
    change = FileChange.fake()
    unchanged = added(RepositoryPath("unchanged.py"), AFTER_BLOB)
    rating = annotated_rating(unchanged, LineAnnotation.fake())

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating_for(RatingTarget.of_change(change)), rating),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems((UnknownRating(rating=rating.target()),))


def test_annotation_problems_of_duplicate_ratings_are_reported_once() -> None:
    change = added(RepositoryPath.fake(), AFTER_BLOB)
    annotation = annotation_on(AnnotationSide.BEFORE, LineNumber.fake())
    rating = annotated_rating(change, annotation)

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating, rating),
        ChangeLineHunks({}),
        BlobLineCounts({AFTER_BLOB: LineCount(10)}),
    )

    assert problems == RatingProblems(
        (
            DuplicateRating(target=rating.target()),
            AnnotationOnMissingSide(target=rating.target(), annotation=annotation),
        )
    )


def test_an_annotation_on_a_file_without_a_line_count_is_unreadable() -> None:
    change = added(RepositoryPath.fake(), AFTER_BLOB)
    annotation = annotation_on(AnnotationSide.AFTER, LineNumber.fake())
    rating = annotated_rating(change, annotation)

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems(
        (AnnotationOnUnreadableFile(target=rating.target(), annotation=annotation),)
    )


def test_annotations_on_a_stale_rating_are_not_checked() -> None:
    path = RepositoryPath.fake()
    change = added(path, AFTER_BLOB)
    old = RatingTarget(path=path, blob=BlobSha("0" * 40))
    stale = rating_for(old).model_copy(
        update={"annotations": (annotation_on(AnnotationSide.BEFORE, LineNumber(5)),)}
    )

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(stale),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems(
        (StaleRating(rating=old, current=RatingTarget.of_change(change)),)
    )


def test_annotated_blobs_are_the_annotated_sides_of_changed_files() -> None:
    annotated = modified(RepositoryPath("annotated.py"), BEFORE_BLOB, AFTER_BLOB)
    plain = modified(RepositoryPath("plain.py"), BlobSha("c" * 40), BlobSha("d" * 40))
    ratings = ratings_file_of(
        annotated_rating(
            annotated, annotation_on(AnnotationSide.BEFORE, LineNumber(1))
        ),
        rating_for(RatingTarget.of_change(plain)),
    )

    blobs = annotated_blobs(FileChanges((annotated, plain)), ratings)

    assert blobs == (BEFORE_BLOB,)


def test_annotated_blobs_skip_duplicate_and_unknown_ratings() -> None:
    first = modified(RepositoryPath("first.py"), BEFORE_BLOB, AFTER_BLOB)
    unchanged = added(RepositoryPath("unchanged.py"), BlobSha("c" * 40))
    rating = annotated_rating(first, annotation_on(AnnotationSide.AFTER, LineNumber(1)))
    duplicate = rating.model_copy(
        update={"annotations": (annotation_on(AnnotationSide.BEFORE, LineNumber(1)),)}
    )
    ratings = ratings_file_of(
        rating,
        duplicate,
        annotated_rating(unchanged, annotation_on(AnnotationSide.AFTER, LineNumber(1))),
    )

    blobs = annotated_blobs(FileChanges((first,)), ratings)

    assert blobs == (AFTER_BLOB,)


def test_a_rating_of_other_hunks_than_the_changed_lines_is_a_mismatch() -> None:
    change = FileChange.fake()
    changed = (LineHunk.fake(),)
    rating = rating_for(RatingTarget.of_change(change))

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating),
        ChangeLineHunks({change.path(): changed}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems(
        (HunkMismatch(target=rating.target(), rated=(None,), changed=changed),)
    )


def test_a_file_without_changed_lines_needs_a_hunk_for_the_whole_change() -> None:
    change = FileChange.fake()
    rated = LineHunk.fake()
    rating = rating_for(RatingTarget.of_change(change)).model_copy(
        update={"hunks": (RatedHunk.of_line_hunk(rated, Probability.fake()),)}
    )

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating),
        ChangeLineHunks({}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems(
        (HunkMismatch(target=rating.target(), rated=(rated,), changed=(None,)),)
    )


def test_the_hunks_of_a_stale_rating_are_not_checked() -> None:
    path = RepositoryPath.fake()
    change = added(path, AFTER_BLOB)
    old = RatingTarget(path=path, blob=BlobSha("0" * 40))

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating_for(old)),
        ChangeLineHunks({path: (LineHunk.fake(),)}),
        BlobLineCounts({}),
    )

    assert problems == RatingProblems(
        (StaleRating(rating=old, current=RatingTarget.of_change(change)),)
    )
