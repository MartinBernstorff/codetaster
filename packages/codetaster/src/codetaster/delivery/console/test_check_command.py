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
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    CategoryDescription,
    PullRequestSummary,
    RatingCategory,
)


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


def write_feature_rating(
    repository: Repository, category: RatingCategory, probability: Probability
) -> None:
    """Rate feature.py, the file the feature branch adds, at `probability`."""
    # The blob SHA of feature.py, which is empty.
    empty_blob = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    ratings = repository.root / ".codetaster" / "ratings.json"
    ratings.parent.mkdir()
    _ = ratings.write_text(
        json.dumps(
            {
                "summary": PullRequestSummary.fake().root,
                "categories": [
                    {
                        "name": category.root,
                        "description": CategoryDescription.fake().root,
                    }
                ],
                "ratings": [
                    {
                        "path": "feature.py",
                        "blob": empty_blob,
                        "probability": probability.root,
                        "category": category.root,
                    }
                ],
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
    category = RatingCategory.fake()
    write_feature_rating(unsampled_repository, category, Probability(1))

    result = run_check(unsampled_repository, CliOptions.fake())

    assert result.exit_code == 0
    [file] = json.loads(result.stdout)["needs-review"]
    assert file["rating"]["category"] == category.root


def test_reports_the_summary_and_category_descriptions(
    unsampled_repository: Repository,
) -> None:
    category = RatingCategory.fake()
    write_feature_rating(unsampled_repository, category, Probability(1))

    result = run_check(unsampled_repository, CliOptions.fake())

    assert json.loads(result.stdout)["overview"] == {
        "summary": PullRequestSummary.fake().root,
        "categories": [
            {"name": category.root, "description": CategoryDescription.fake().root}
        ],
    }


def test_needs_review_threshold_overrides_the_configured_one(
    unsampled_repository: Repository,
) -> None:
    rating = Probability(0.5)
    write_feature_rating(unsampled_repository, RatingCategory.fake(), rating)

    result = run_check(
        unsampled_repository,
        CliOptions(("--needs-review-threshold", str(rating.root))),
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["needs_review_threshold"] == rating.root
    [file] = report["needs-review"]
    assert file["path"] == "feature.py"


def test_a_needs_review_threshold_above_1_is_an_error(repository: Repository) -> None:
    result = run_check(repository, CliOptions(("--needs-review-threshold", "1.5")))

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


def test_commented_files_add_sampled_files(tmp_path: Path) -> None:
    # feature.py's draw is about 0.31: above 0.2, below (2 + 3) / (10 + 3 + 1).
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "main"\nbase_probability = 0.2\n'),
    )
    commented = 3
    viewed = 1

    without = run_check(repository, CliOptions.fake())
    with_evidence = run_check(
        repository,
        CliOptions(
            ("--commented-files", str(commented), "--viewed-files", str(viewed))
        ),
    )

    assert json.loads(without.stdout)["sampled"] == []
    report = json.loads(with_evidence.stdout)
    assert report["sampling"]["commented_files"] == commented
    assert report["sampling"]["viewed_files"] == viewed
    [file] = report["sampled"]
    assert file["path"] == "feature.py"


def test_a_negative_commented_file_count_is_an_error(repository: Repository) -> None:
    result = run_check(repository, CliOptions(("--commented-files", "-1")))

    assert result.exit_code != 0
