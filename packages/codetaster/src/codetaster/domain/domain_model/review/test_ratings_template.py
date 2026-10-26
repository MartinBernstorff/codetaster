import json

from hypothesis import given
from hypothesis import strategies as st
from safe_result import Err, Ok

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import (
    ChangeLineHunks,
    FileChange,
    FileChanges,
    LineHunk,
)
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    FileRatings,
    RatingsFile,
    RatingsFileContent,
    RatingTarget,
    parse_ratings_file,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.domain_model.review.test_strategies import (
    file_changes,
    fill_template,
    line_hunks,
    ratings_of,
)


@given(st.lists(file_changes()))
def test_has_one_entry_per_changed_file(changes: list[FileChange]) -> None:
    template = RatingsTemplate.of_changes(
        FileChanges(tuple(changes)), ChangeLineHunks({})
    )

    assert [entry.target() for entry in template.ratings] == [
        RatingTarget.of_change(change) for change in changes
    ]


def test_leaves_the_category_blank() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake(), ChangeLineHunks({}))

    [entry] = json.loads(template.model_dump_json())["ratings"]
    assert entry["category"] is None


def test_lists_each_hunk_with_its_probability_blank() -> None:
    change = FileChange.fake()
    hunk = LineHunk.fake()
    template = RatingsTemplate.of_changes(
        FileChanges((change,)), ChangeLineHunks({change.path(): (hunk, hunk)})
    )

    [entry] = json.loads(template.model_dump_json())["ratings"]
    blank_hunk = hunk.model_dump(mode="json") | {"probability": None}
    assert entry["hunks"] == [blank_hunk, blank_hunk]


def test_a_change_without_changed_lines_has_one_blank_hunk_without_lines() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake(), ChangeLineHunks({}))

    [entry] = json.loads(template.model_dump_json())["ratings"]
    blank_hunk: dict[str, None] = {"before": None, "after": None, "probability": None}
    assert entry["hunks"] == [blank_hunk]


def test_leaves_the_summary_blank() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake(), ChangeLineHunks({}))

    assert json.loads(template.model_dump_json())["summary"] is None


def test_shows_one_blank_category() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake(), ChangeLineHunks({}))

    blank_category: dict[str, None] = {"name": None, "description": None}

    assert json.loads(template.model_dump_json())["categories"] == [blank_category]


def test_shows_one_blank_annotation_per_entry() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake(), ChangeLineHunks({}))

    blank_annotation: dict[str, str | None] = {
        "side": "after",
        "line": None,
        "text": None,
    }

    [entry] = json.loads(template.model_dump_json())["ratings"]
    assert entry["annotations"] == [blank_annotation]


def test_does_not_parse_as_a_ratings_file_until_filled() -> None:
    template = RatingsTemplate.of_changes(FileChanges.fake(), ChangeLineHunks({}))

    result = parse_ratings_file(
        RatingsFileContent(template.model_dump_json()), Location.fake()
    )

    assert isinstance(result, Err)


@given(st.data(), st.lists(file_changes(), min_size=1))
def test_any_fill_parses_as_a_ratings_file(
    data: st.DataObject, changes: list[FileChange]
) -> None:
    hunks = ChangeLineHunks(
        {change.path(): data.draw(line_hunks()) for change in changes}
    )
    template = RatingsTemplate.of_changes(FileChanges(tuple(changes)), hunks)
    filled = fill_template(
        template,
        [
            data.draw(ratings_of(change, hunks.hunks_to_rate(change)))
            for change in changes
        ],
    )

    result = parse_ratings_file(filled, Location.fake())

    match result:
        case Ok(RatingsFile(ratings=ratings)):
            assert [rating.target() for rating in ratings.root] == [
                entry.target() for entry in template.ratings
            ]
        case _:
            raise AssertionError(result)


def test_a_fill_that_leaves_the_placeholder_annotation_has_no_annotations() -> None:
    change = FileChange.fake()
    template = RatingsTemplate.of_changes(FileChanges((change,)), ChangeLineHunks({}))
    filled = json.loads(fill_template(template, [FileRating.fake()]).root)
    [template_entry] = json.loads(template.model_dump_json())["ratings"]
    filled["ratings"][0]["annotations"] = template_entry["annotations"]

    result = parse_ratings_file(RatingsFileContent(json.dumps(filled)), Location.fake())

    match result:
        case Ok(RatingsFile(ratings=FileRatings(root=(rating,)))):
            assert rating.annotations == ()
        case _:
            raise AssertionError(result)
