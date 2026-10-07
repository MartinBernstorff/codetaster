import json

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
    FileRating,
    RatingsFile,
    RatingsFileContent,
    RatingTarget,
    parse_ratings_file,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.domain_model.review.ratings_validation import (
    DuplicateRating,
    RatingProblems,
    StaleRating,
    UnknownRating,
    UnratedFile,
    find_rating_problems,
)
from codetaster.domain.domain_model.review.test_strategies import (
    file_changes,
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
        RatingsFile(ratings=(rating_for(RatingTarget.of_change(change)),)),
    )

    assert problems == RatingProblems(())


def test_a_changed_file_without_a_rating_is_unrated() -> None:
    target = RatingTarget.of_change(FileChange.fake())

    problems = find_rating_problems(
        FileChanges((FileChange.fake(),)), RatingsFile(ratings=())
    )

    assert problems == RatingProblems((UnratedFile(target=target),))


def test_a_rating_for_an_older_blob_is_stale() -> None:
    path = RepositoryPath.fake()
    current_blob = BlobSha("1" * 40)
    current = RatingTarget(path=path, blob=current_blob)
    old = RatingTarget(path=path, blob=BlobSha("2" * 40))

    problems = find_rating_problems(
        FileChanges((added(path, current_blob),)),
        RatingsFile(ratings=(rating_for(old),)),
    )

    assert problems == RatingProblems((StaleRating(rating=old, current=current),))


def test_a_rating_for_an_unchanged_file_is_unknown() -> None:
    change = FileChange.fake()
    unknown = RatingTarget(path=RepositoryPath("unchanged.py"), blob=BlobSha.fake())

    problems = find_rating_problems(
        FileChanges((change,)),
        RatingsFile(
            ratings=(
                rating_for(RatingTarget.of_change(change)),
                rating_for(unknown),
            )
        ),
    )

    assert problems == RatingProblems((UnknownRating(rating=unknown),))


def test_two_ratings_for_the_same_file_are_duplicates() -> None:
    change = FileChange.fake()
    target = RatingTarget.of_change(change)

    problems = find_rating_problems(
        FileChanges((change,)),
        RatingsFile(ratings=(rating_for(target), rating_for(target))),
    )

    assert problems == RatingProblems((DuplicateRating(target=target),))


@given(st.data(), st.lists(file_changes(), unique_by=lambda change: change.path()))
def test_any_fill_of_the_template_has_no_problems(
    data: st.DataObject, changes: list[FileChange]
) -> None:
    file_changes_ = FileChanges(tuple(changes))
    template = RatingsTemplate.of_changes(file_changes_)
    filled = {
        "ratings": [
            entry.model_dump(mode="json")
            | {"probability": rating.probability.root, "reason": rating.reason.root}
            for entry, rating in zip(
                template.ratings,
                (data.draw(ratings_of(change)) for change in changes),
                strict=True,
            )
        ]
    }
    parsed = parse_ratings_file(RatingsFileContent(json.dumps(filled)), Location.fake())
    assert isinstance(parsed, Ok)

    problems = find_rating_problems(file_changes_, parsed.value)

    assert problems == RatingProblems(())
