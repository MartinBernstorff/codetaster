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


def test_a_rated_file_needs_review(tmp_path: Path) -> None:
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "main"\nbase_probability = 0\n'),
    )
    reason = "It is the feature."
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
                        "reason": reason,
                    }
                ]
            }
        )
    )

    result = run_check(repository, CliOptions.fake())

    assert result.exit_code == 0
    [file] = json.loads(result.stdout)["needs-review"]
    assert file["rating"]["reason"] == reason


def test_an_invalid_ratings_file_exits_non_zero(repository: Repository) -> None:
    ratings = repository.root / ".codetaster" / "ratings.json"
    ratings.parent.mkdir()
    _ = ratings.write_text("not json")

    result = run_check(repository, CliOptions.fake())

    assert result.exit_code != 0


def test_missing_review_section_exits_non_zero(tmp_path: Path) -> None:
    repository = Repository(tmp_path, project_config=None)

    result = run_check(repository, CliOptions.fake())

    assert result.exit_code != 0
