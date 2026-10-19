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
    fill_template,
    ratings_of,
)


@given(st.lists(file_changes()))
def test_has_one_entry_per_changed_file(changes: list[FileChange]) -> None:
    template = RatingsTemplate.of_changes(FileChanges(tuple(changes)))

    assert [entry.target() for entry in template.ratings] == [
        RatingTarget.of_change(change) for change in changes
    ]


def test_leaves_probability_and_category_blank() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake())

    [entry] = json.loads(template.model_dump_json())["ratings"]
    assert entry["probability"] is None
    assert entry["category"] is None


def test_leaves_the_summary_blank() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake())

    assert json.loads(template.model_dump_json())["summary"] is None


def test_shows_one_blank_category() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake())

    assert json.loads(template.model_dump_json())["categories"] == [
        {"name": None, "description": None}
    ]


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
    filled = fill_template(
        template, [data.draw(ratings_of(change)) for change in changes]
    )

    result = parse_ratings_file(filled, Location.fake())

    match result:
        case Ok(RatingsFile(ratings=ratings)):
            assert [rating.target() for rating in ratings.root] == [
                entry.target() for entry in template.ratings
            ]
        case _:
            raise AssertionError(result)
