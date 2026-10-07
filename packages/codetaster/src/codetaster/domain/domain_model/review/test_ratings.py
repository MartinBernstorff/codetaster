import pytest
from hypothesis import given
from hypothesis import strategies as st
from safe_result import Err, Ok

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    RatingsFile,
    RatingsFileContent,
    RatingTarget,
    parse_ratings_file,
)
from codetaster.domain.domain_model.review.test_strategies import (
    blob_shas,
    file_changes,
    ratings_of,
)


def test_parses_a_valid_file() -> None:
    ratings = RatingsFile.fake()
    content = RatingsFileContent(ratings.model_dump_json(indent=2))

    assert parse_ratings_file(content, Location.fake()) == Ok(ratings)


def test_parses_the_documented_format() -> None:
    content = RatingsFileContent(
        '{"ratings": [{"path": "a.py", "blob": null, "probability": 1, '
        '"reason": "Why."}]}'
    )

    assert isinstance(parse_ratings_file(content, Location.fake()), Ok)


@pytest.mark.parametrize(
    "content",
    [
        RatingsFileContent("not json"),
        RatingsFileContent("[]"),
        RatingsFileContent(
            '{"ratings": [{"path": "a.py", "blob": null, "probability": 1.5, '
            '"reason": "Why."}]}'
        ),
        RatingsFileContent(
            '{"ratings": [{"path": "a.py", "blob": null, "probability": 1, '
            '"reason": ""}]}'
        ),
        RatingsFileContent(
            '{"ratings": [{"path": "a.py", "blob": null, "probability": 1}]}'
        ),
        RatingsFileContent(
            '{"ratings": [{"path": "a.py", "blob": null, "probability": 1, '
            '"reason": "Why.", "extra": 1}]}'
        ),
    ],
    ids=[
        "not-json",
        "not-an-object",
        "probability-above-one",
        "empty-reason",
        "no-reason",
        "unknown-field",
    ],
)
def test_rejects_an_invalid_file(content: RatingsFileContent) -> None:
    location = Location.fake()

    match parse_ratings_file(content, location):
        case Err(error):
            assert error.location == location
        case Ok(value):
            pytest.fail(f"expected an error, got {value!r}")


def test_a_rating_applies_to_the_change_it_names() -> None:
    change = FileChange.fake()
    rating = FileRating.fake().model_copy(
        update=RatingTarget.of_change(change).model_dump()
    )

    assert RatingsFile(ratings=(rating,)).rating_for(change) == rating


def test_a_deleted_file_is_rated_with_a_null_blob() -> None:
    change = FileChange(before=FileVersion.fake(), after=None)
    rating = FileRating.fake().model_copy(update={"path": change.path(), "blob": None})

    assert RatingsFile(ratings=(rating,)).rating_for(change) == rating


def test_the_highest_of_several_matching_ratings_applies() -> None:
    change = FileChange.fake()
    low = FileRating.fake().model_copy(update={"probability": Probability(0.1)})
    high = FileRating.fake().model_copy(update={"probability": Probability(0.9)})

    assert RatingsFile(ratings=(low, high)).rating_for(change) == high


@given(change=file_changes(), data=st.data())
def test_a_rating_for_another_blob_does_not_apply(
    change: FileChange, data: st.DataObject
) -> None:
    rating = data.draw(ratings_of(change))
    other_blob = data.draw(blob_shas().filter(lambda blob: blob != rating.blob))
    stale = rating.model_copy(update={"blob": other_blob})

    assert RatingsFile(ratings=(stale,)).rating_for(change) is None


def test_a_rating_for_another_path_does_not_apply() -> None:
    change = FileChange.fake()
    rating = FileRating.fake().model_copy(update={"path": RepositoryPath("other.py")})

    assert RatingsFile(ratings=(rating,)).rating_for(change) is None


def test_target_of_a_change_is_its_path_and_after_blob() -> None:
    blob = BlobSha("b" * 40)
    before = FileVersion.fake()
    after = before.model_copy(update={"blob": blob})

    target = RatingTarget.of_change(FileChange(before=before, after=after))

    assert target == RatingTarget(path=after.path, blob=blob)
