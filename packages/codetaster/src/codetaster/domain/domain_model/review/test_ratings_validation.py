from hypothesis import given
from hypothesis import strategies as st
from safe_result import Ok

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileChanges,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.ratings import (
    DescribedCategory,
    FileRating,
    RatingCategory,
    RatingTarget,
    parse_ratings_file,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.domain_model.review.ratings_validation import (
    DuplicateCategory,
    DuplicateRating,
    RatingProblems,
    StaleRating,
    UndeclaredCategory,
    UnknownRating,
    UnratedFile,
    UnusedCategory,
    find_rating_problems,
)
from codetaster.domain.domain_model.review.test_strategies import (
    file_changes,
    fill_template,
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
    )

    assert problems == RatingProblems(())


def test_a_changed_file_without_a_rating_is_unrated() -> None:
    target = RatingTarget.of_change(FileChange.fake())

    problems = find_rating_problems(
        FileChanges((FileChange.fake(),)), ratings_file_of()
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
    )

    assert problems == RatingProblems((UnknownRating(rating=unknown),))


def test_two_ratings_for_the_same_file_are_duplicates() -> None:
    change = FileChange.fake()
    target = RatingTarget.of_change(change)

    problems = find_rating_problems(
        FileChanges((change,)),
        ratings_file_of(rating_for(target), rating_for(target)),
    )

    assert problems == RatingProblems((DuplicateRating(target=target),))


@given(st.data(), st.lists(file_changes(), unique_by=lambda change: change.path()))
def test_any_fill_of_the_template_has_no_problems(
    data: st.DataObject, changes: list[FileChange]
) -> None:
    file_changes_ = FileChanges(tuple(changes))
    template = RatingsTemplate.of_changes(file_changes_)
    filled = fill_template(
        template, [data.draw(ratings_of(change)) for change in changes]
    )
    parsed = parse_ratings_file(filled, Location.fake())
    assert isinstance(parsed, Ok)

    problems = find_rating_problems(file_changes_, parsed.value)

    assert problems == RatingProblems(())


def test_a_category_that_is_not_described_is_undeclared() -> None:
    change = FileChange.fake()
    rating = rating_for(RatingTarget.of_change(change))
    ratings = ratings_file_of(rating).model_copy(update={"categories": ()})

    problems = find_rating_problems(FileChanges((change,)), ratings)

    assert problems == RatingProblems((UndeclaredCategory(category=rating.category),))


def test_a_described_category_without_files_is_unused() -> None:
    change = FileChange.fake()
    unused = DescribedCategory.fake().model_copy(
        update={"name": RatingCategory("Unused")}
    )
    ratings = ratings_file_of(rating_for(RatingTarget.of_change(change)))
    ratings = ratings.model_copy(update={"categories": (*ratings.categories, unused)})

    problems = find_rating_problems(FileChanges((change,)), ratings)

    assert problems == RatingProblems((UnusedCategory(category=unused.name),))


def test_a_category_described_twice_is_a_duplicate() -> None:
    change = FileChange.fake()
    ratings = ratings_file_of(rating_for(RatingTarget.of_change(change)))
    ratings = ratings.model_copy(update={"categories": ratings.categories * 2})
    [category] = {category.name for category in ratings.categories}

    problems = find_rating_problems(FileChanges((change,)), ratings)

    assert problems == RatingProblems((DuplicateCategory(category=category),))
