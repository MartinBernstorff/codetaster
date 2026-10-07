"""The printed instructions and template. Building the template is tested in the domain."""

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


def test_prints_a_template_entry_for_the_changed_file(
    repository: Repository,
) -> None:
    # The blob SHA of feature.py, which is empty.
    empty_blob = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"

    result = run_template(repository, CliOptions.fake())

    assert result.exit_code == 0
    # The JSON template follows the instructions.
    template = json.loads(result.stdout[result.stdout.index("\n{\n") :])
    assert template == {
        "ratings": [
            {
                "path": "feature.py",
                "blob": empty_blob,
                "probability": None,
                "reason": None,
            }
        ]
    }


def test_instructions_name_the_ratings_file_and_the_validate_command(
    repository: Repository,
) -> None:
    ratings_path = ".codetaster/ratings.json"
    validate = f"codetaster ratings validate {repository.root.resolve()}"

    result = run_template(repository, CliOptions.fake())

    assert ratings_path in result.stdout
    assert validate in result.stdout


def test_instructions_give_the_base_probability(tmp_path: Path) -> None:
    base_probability = "0.25"
    repository = Repository(
        tmp_path,
        TomlText(
            f'[review]\nbase_branch = "main"\nbase_probability = {base_probability}\n'
        ),
    )

    result = run_template(repository, CliOptions.fake())

    assert base_probability in result.stdout


def test_base_option_is_passed_on_to_validate(tmp_path: Path) -> None:
    repository = Repository(
        tmp_path,
        TomlText('[review]\nbase_branch = "no-such-branch"\nbase_probability = 1\n'),
    )
    base = "main"

    result = run_template(repository, CliOptions(("--base", base)))

    assert result.exit_code == 0
    assert f"--base {base}" in result.stdout


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
