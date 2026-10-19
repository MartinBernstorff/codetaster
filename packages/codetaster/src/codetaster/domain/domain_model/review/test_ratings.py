import json

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import JsonValue, RootModel
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
    DescribedCategory,
    FileRating,
    FileRatings,
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
        '{"summary": "Retries payments.", '
        '"categories": [{"name": "Payments", "description": "Retries."}], '
        '"ratings": [{"path": "a.py", "blob": null, "probability": 1, '
        '"category": "Payments"}]}'
    )

    assert isinstance(parse_ratings_file(content, Location.fake()), Ok)


def fake_file_with(**fields: JsonValue) -> RatingsFileContent:
    """The fake ratings file, with `fields` replaced."""
    return RatingsFileContent(
        json.dumps(RatingsFile.fake().model_dump(mode="json") | fields)
    )


def fake_rating_with(**fields: JsonValue) -> RatingsFileContent:
    """The fake ratings file, with `fields` replaced in its one rating."""
    return fake_file_with(ratings=[FileRating.fake().model_dump(mode="json") | fields])


def fake_category_with(**fields: JsonValue) -> RatingsFileContent:
    """The fake ratings file, with `fields` replaced in its one category."""
    return fake_file_with(
        categories=[DescribedCategory.fake().model_dump(mode="json") | fields]
    )


class FieldName(RootModel[str]):
    @staticmethod
    def fake() -> FieldName:
        return FieldName("summary")


def fake_file_without(field: FieldName) -> RatingsFileContent:
    document = RatingsFile.fake().model_dump(mode="json")
    del document[field.root]
    return RatingsFileContent(json.dumps(document))


@pytest.mark.parametrize(
    "content",
    [
        RatingsFileContent("not json"),
        RatingsFileContent("[]"),
        fake_rating_with(probability=1.5),
        fake_rating_with(category=""),
        fake_rating_with(category=None),
        fake_rating_with(extra=1),
        fake_file_without(FieldName("summary")),
        fake_file_with(summary=""),
        fake_file_without(FieldName("categories")),
        fake_category_with(description=""),
        fake_category_with(description=None),
        fake_category_with(extra=1),
    ],
    ids=[
        "not-json",
        "not-an-object",
        "probability-above-one",
        "empty-category",
        "no-category",
        "unknown-rating-field",
        "no-summary",
        "empty-summary",
        "no-categories",
        "empty-description",
        "no-description",
        "unknown-category-field",
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

    assert FileRatings((rating,)).rating_for(change) == rating


def test_a_deleted_file_is_rated_with_a_null_blob() -> None:
    change = FileChange(before=FileVersion.fake(), after=None)
    rating = FileRating.fake().model_copy(update={"path": change.path(), "blob": None})

    assert FileRatings((rating,)).rating_for(change) == rating


def test_the_highest_of_several_matching_ratings_applies() -> None:
    change = FileChange.fake()
    low = FileRating.fake().model_copy(update={"probability": Probability(0.1)})
    high = FileRating.fake().model_copy(update={"probability": Probability(0.9)})

    assert FileRatings((low, high)).rating_for(change) == high


@given(change=file_changes(), data=st.data())
def test_a_rating_for_another_blob_does_not_apply(
    change: FileChange, data: st.DataObject
) -> None:
    rating = data.draw(ratings_of(change))
    other_blob = data.draw(blob_shas().filter(lambda blob: blob != rating.blob))
    stale = rating.model_copy(update={"blob": other_blob})

    assert FileRatings((stale,)).rating_for(change) is None


def test_a_rating_for_another_path_does_not_apply() -> None:
    change = FileChange.fake()
    rating = FileRating.fake().model_copy(update={"path": RepositoryPath("other.py")})

    assert FileRatings((rating,)).rating_for(change) is None


def test_target_of_a_change_is_its_path_and_after_blob() -> None:
    blob = BlobSha("b" * 40)
    before = FileVersion.fake()
    after = before.model_copy(update={"blob": blob})

    target = RatingTarget.of_change(FileChange(before=before, after=after))

    assert target == RatingTarget(path=after.path, blob=blob)
