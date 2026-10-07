"""Exit codes and flag wiring. The check itself is tested in the domain."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from codetaster.delivery.console.app import app
from codetaster.delivery.console.test_repositories import (
    CliOptions,
    Repository,
    TomlText,
)
from codetaster.domain.domain_model.review.ratings import RatingReason


def run_check(repository: Repository, options: CliOptions) -> Result:
    """Run `codetaster check` on `repository`."""
    return CliRunner().invoke(
        app,
        ["check", str(repository.root), *options.root],
        # Keep the developer's own config out of the test.
        env={"XDG_CONFIG_HOME": str(repository.root / "xdg")},
    )


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    return Repository(tmp_path, TomlText.fake())


def test_succeeds_when_files_need_review(repository: Repository) -> None:
    result = run_check(repository, CliOptions(("--format", "json")))

    assert result.exit_code == 0
    assert json.loads(result.stdout)["needs_review"] is True


def test_fail_on_needs_review_exits_non_zero_when_a_file_needs_review(
    repository: Repository,
) -> None:
    result = run_check(repository, CliOptions(("--fail-on-needs-review",)))

    assert result.exit_code != 0


def test_fail_on_needs_review_succeeds_when_no_file_needs_review(
    tmp_path: Path,
) -> None:
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "main"\nbase_probability = 0\n'),
    )

    result = run_check(repository, CliOptions(("--fail-on-needs-review",)))

    assert result.exit_code == 0


def test_base_option_overrides_the_configured_base(tmp_path: Path) -> None:
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "no-such-branch"\nbase_probability = 1\n'),
    )
    base = "main"

    result = run_check(repository, CliOptions(("--base", base)))

    assert result.exit_code == 0
    assert json.loads(result.stdout)["base"]["ref"] == base


def test_a_path_rule_samples_a_matching_file(tmp_path: Path) -> None:
    pattern = "*.py"
    repository = Repository(
        tmp_path,
        TomlText(
            '[review]\nbase_branch = "main"\nbase_probability = 0\n'
            f'[[review.path_rules]]\npattern = "{pattern}"\nprobability = 1\n'
        ),
    )

    result = run_check(repository, CliOptions.fake())

    assert result.exit_code == 0
    [file] = json.loads(result.stdout)["sampled"]
    assert file["path_rule"]["pattern"] == pattern


def write_feature_rating(repository: Repository, reason: RatingReason) -> None:
    """Rate feature.py, the file the feature branch adds, at 1."""
    # The blob SHA of feature.py, which is empty.
    empty_blob = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    ratings = repository.root / ".codetaster" / "ratings.json"
    ratings.parent.mkdir()
    _ = ratings.write_text(
        json.dumps(
            {
                "ratings": [
                    {
                        "path": "feature.py",
                        "blob": empty_blob,
                        "probability": 1,
                        "reason": reason.root,
                    }
                ]
            }
        )
    )


@pytest.fixture
def unsampled_repository(tmp_path: Path) -> Repository:
    return Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "main"\nbase_probability = 0\n'),
    )


def test_a_rated_file_needs_review(unsampled_repository: Repository) -> None:
    reason = RatingReason("It is the feature.")
    write_feature_rating(unsampled_repository, reason)

    result = run_check(unsampled_repository, CliOptions.fake())

    assert result.exit_code == 0
    [file] = json.loads(result.stdout)["needs-review"]
    assert file["rating"]["reason"] == reason.root


def test_top_rated_percentage_overrides_the_configured_one(
    unsampled_repository: Repository,
) -> None:
    write_feature_rating(unsampled_repository, RatingReason.fake())
    percentage = 0

    result = run_check(
        unsampled_repository, CliOptions(("--top-rated-percentage", str(percentage)))
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["top_rated_percentage"] == percentage
    assert report["needs-review"] == []


def test_a_top_rated_percentage_above_100_is_an_error(repository: Repository) -> None:
    result = run_check(repository, CliOptions(("--top-rated-percentage", "101")))

    assert result.exit_code != 0


def test_an_invalid_ratings_file_is_reported_and_every_file_is_unrated(
    repository: Repository,
) -> None:
    ratings = repository.root / ".codetaster" / "ratings.json"
    ratings.parent.mkdir()
    _ = ratings.write_text("not json")

    result = run_check(repository, CliOptions.fake())

    assert result.exit_code == 0
    assert str(ratings) in result.stderr
    report = json.loads(result.stdout)
    assert str(ratings) in report["ratings_error"]
    assert {
        file["unrated"]
        for group in ("needs-review", "sampled", "no-review")
        for file in report[group]
    } == {True}


def test_a_valid_ratings_file_has_no_ratings_error(repository: Repository) -> None:
    result = run_check(repository, CliOptions.fake())

    assert json.loads(result.stdout)["ratings_error"] is None


def test_missing_review_section_exits_non_zero(tmp_path: Path) -> None:
    repository = Repository(tmp_path, project_config=None)

    result = run_check(repository, CliOptions.fake())

    assert result.exit_code != 0
