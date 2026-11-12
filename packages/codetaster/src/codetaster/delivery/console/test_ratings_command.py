"""The written and printed template. Building the template is tested in the domain."""

import json
from pathlib import Path

import pytest
from pydantic import JsonValue
from typer.testing import CliRunner, Result

from codetaster.delivery.console.app import app
from codetaster.delivery.console.test_repositories import (
    CliOptions,
    FeatureFileText,
    Repository,
    TomlText,
)
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.changes import BlobSha, RepositoryPath
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    LineAnnotation,
    RatingsFile,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.domain_model.review.test_strategies import ratings_file_of


def run_template(repository: Repository, options: CliOptions) -> Result:
    """Run `codetaster ratings template` on `repository`."""
    return CliRunner().invoke(
        app,
        ["ratings", "template", str(repository.root), *options.root],
        # Keep the developer's own config out of the test.
        env={"XDG_CONFIG_HOME": str(repository.root / "xdg")},
    )


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    return Repository(tmp_path, TomlText.fake())


def ratings_location(repository: Repository) -> Location:
    """Where `TomlText.fake()` puts the ratings file."""
    return Location(repository.root / ".codetaster" / "ratings.json")


def expected_template() -> JsonValue:
    # The blob SHA of feature.py, which is empty.
    empty_blob = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    return {
        "summary": None,
        "categories": [{"name": None, "description": None}],
        "ratings": [
            {
                "path": "feature.py",
                "blob": empty_blob,
                "probability": None,
                "category": None,
                "annotations": [{"side": "after", "line": None, "text": None}],
            }
        ],
    }


def test_writes_the_template_to_the_ratings_path_and_prints_it(
    repository: Repository,
) -> None:
    location = ratings_location(repository)

    result = run_template(repository, CliOptions.fake())

    assert result.exit_code == 0
    assert json.loads(location.root.read_text()) == expected_template()
    assert str(location.root.resolve()) in result.stdout


def test_stdout_prints_the_template_without_writing_it(
    repository: Repository,
) -> None:
    result = run_template(repository, CliOptions(("--stdout",)))

    assert result.exit_code == 0
    assert json.loads(result.stdout) == expected_template()
    assert not ratings_location(repository).root.exists()


def test_replaces_an_existing_ratings_file(repository: Repository) -> None:
    write_ratings(repository, filled_template(repository))

    result = run_template(repository, CliOptions.fake())

    assert result.exit_code == 0
    assert json.loads(ratings_location(repository).root.read_text()) == (
        expected_template()
    )


def test_unknown_base_exits_non_zero(tmp_path: Path) -> None:
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "no-such-branch"\nbase_probability = 1\n'),
    )

    result = run_template(repository, CliOptions.fake())

    assert result.exit_code != 0


def test_missing_review_section_exits_non_zero(tmp_path: Path) -> None:
    repository = Repository(tmp_path, project_config=None)

    result = run_template(repository, CliOptions.fake())

    assert result.exit_code != 0


def run_validate(repository: Repository, options: CliOptions) -> Result:
    """Run `codetaster ratings validate` on `repository`."""
    return CliRunner().invoke(
        app,
        ["ratings", "validate", str(repository.root), *options.root],
        env={"XDG_CONFIG_HOME": str(repository.root / "xdg")},
    )


def written_template(repository: Repository) -> RatingsTemplate:
    """The template `ratings template` wrote, replacing any ratings file."""
    result = run_template(repository, CliOptions.fake())
    assert result.exit_code == 0
    return RatingsTemplate.model_validate_json(
        ratings_location(repository).root.read_text()
    )


def write_ratings(
    repository: Repository, ratings: RatingsTemplate | RatingsFile
) -> None:
    location = ratings_location(repository).root
    location.parent.mkdir(exist_ok=True)
    _ = location.write_text(ratings.model_dump_json())


def filled_template(repository: Repository) -> RatingsFile:
    """The template from `ratings template`, with every entry rated."""
    template = written_template(repository)
    return ratings_file_of(
        *(
            FileRating.fake().model_copy(
                update={"path": entry.path, "blob": entry.blob}
            )
            for entry in template.ratings
        )
    )


def test_a_filled_template_is_valid(repository: Repository) -> None:
    write_ratings(repository, filled_template(repository))

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 0


def test_an_unrated_file_exits_non_zero_and_names_the_file(
    repository: Repository,
) -> None:
    unrated = "feature.py"
    write_ratings(repository, ratings_file_of())

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1
    assert unrated in result.stderr


def test_a_stale_rating_gives_the_current_blob(repository: Repository) -> None:
    # The blob SHA of feature.py, which is empty.
    current_blob = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    [rating] = filled_template(repository).ratings.root
    stale = rating.model_copy(update={"blob": BlobSha("0" * 40)})
    write_ratings(repository, ratings_file_of(stale))

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1
    assert current_blob in result.stderr


def test_an_unknown_rating_exits_non_zero_and_names_the_path(
    repository: Repository,
) -> None:
    unknown = "unchanged.py"
    [rating] = filled_template(repository).ratings.root
    other = rating.model_copy(update={"path": RepositoryPath(unknown)})
    write_ratings(repository, ratings_file_of(rating, other))

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1
    assert unknown in result.stderr


def test_a_duplicate_rating_exits_non_zero(repository: Repository) -> None:
    [rating] = filled_template(repository).ratings.root
    write_ratings(repository, ratings_file_of(rating, rating))

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1


def test_an_annotation_past_the_last_line_exits_non_zero_and_names_the_file(
    repository: Repository,
) -> None:
    # feature.py is empty, so it has no line 1.
    path = "feature.py"
    ratings = filled_template(repository)
    [rating] = ratings.ratings.root
    annotated = rating.model_copy(update={"annotations": (LineAnnotation.fake(),)})
    write_ratings(repository, ratings_file_of(annotated))

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1
    assert path in result.stderr


def test_an_annotation_on_an_existing_line_is_valid(repository: Repository) -> None:
    repository.commit_feature_file(FeatureFileText.fake())
    ratings = filled_template(repository)
    [rating] = ratings.ratings.root
    annotated = rating.model_copy(update={"annotations": (LineAnnotation.fake(),)})
    write_ratings(repository, ratings_file_of(annotated))

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 0


def test_an_undescribed_category_exits_non_zero_and_names_it(
    repository: Repository,
) -> None:
    ratings = filled_template(repository)
    [rating] = ratings.ratings.root
    write_ratings(repository, ratings.model_copy(update={"categories": ()}))

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1
    assert rating.category.root in result.stderr


def test_a_missing_ratings_file_exits_non_zero_and_names_its_location(
    repository: Repository,
) -> None:
    ratings_path = ".codetaster/ratings.json"

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1
    assert ratings_path in result.stderr


def test_an_unfilled_template_exits_non_zero_and_names_the_field(
    repository: Repository,
) -> None:
    field = "probability"
    _ = written_template(repository)

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1
    assert field in result.stderr


def test_validate_base_option_overrides_the_configured_base(tmp_path: Path) -> None:
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "no-such-branch"\nbase_probability = 1\n'),
    )
    write_ratings(repository, ratings_file_of())
    unrated = "feature.py"

    result = run_validate(repository, CliOptions(("--base", "main")))

    assert unrated in result.stderr


def test_a_missing_ratings_file_names_the_template_command_with_the_base(
    tmp_path: Path,
) -> None:
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "no-such-branch"\nbase_probability = 1\n'),
    )
    base = "main"

    result = run_validate(repository, CliOptions(("--base", base)))

    assert result.exit_code == 1
    assert (
        f"ratings template {repository.root.resolve()} --base {base}" in result.stderr
    )


def test_validate_with_an_unknown_base_exits_non_zero(tmp_path: Path) -> None:
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "no-such-branch"\nbase_probability = 1\n'),
    )

    result = run_validate(repository, CliOptions.fake())

    assert result.exit_code == 1
