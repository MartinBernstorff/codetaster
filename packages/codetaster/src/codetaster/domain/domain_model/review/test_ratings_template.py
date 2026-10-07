import json

from hypothesis import given
from hypothesis import strategies as st
from safe_result import Err, Ok

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import FileChange, FileChanges
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileContent,
    RatingTarget,
    parse_ratings_file,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.domain_model.review.test_strategies import (
    file_changes,
    ratings_of,
)


@given(st.lists(file_changes()))
def test_has_one_entry_per_changed_file(changes: list[FileChange]) -> None:
    template = RatingsTemplate.of_changes(FileChanges(tuple(changes)))

    assert [entry.target() for entry in template.ratings] == [
        RatingTarget.of_change(change) for change in changes
    ]


def test_leaves_probability_and_reason_blank() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake())

    [entry] = json.loads(template.model_dump_json())["ratings"]
    assert entry["probability"] is None
    assert entry["reason"] is None


def test_does_not_parse_as_a_ratings_file_until_filled() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake())

    result = parse_ratings_file(
        RatingsFileContent(template.model_dump_json()), Location.fake()
    )

    assert isinstance(result, Err)


@given(st.data(), st.lists(file_changes(), min_size=1))
def test_any_fill_parses_as_a_ratings_file(
    data: st.DataObject, changes: list[FileChange]
) -> None:
    template = RatingsTemplate.of_changes(FileChanges(tuple(changes)))
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

    result = parse_ratings_file(RatingsFileContent(json.dumps(filled)), Location.fake())

    match result:
        case Ok(RatingsFile(ratings=ratings)):
            assert [rating.target() for rating in ratings] == [
                entry.target() for entry in template.ratings
            ]
        case _:
            raise AssertionError(result)
