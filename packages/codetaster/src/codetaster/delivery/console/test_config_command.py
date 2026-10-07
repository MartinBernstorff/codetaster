from typer.testing import CliRunner

from codetaster.delivery.console.app import app
from codetaster.domain.domain_model.configuration.review_settings import (
    ReviewSettings,
)
from codetaster.domain.domain_model.configuration.settings import Settings


def test_options_lists_every_setting() -> None:
    expected = [
        *Settings.model_fields,
        *(f"[review] {name}" for name in ReviewSettings.model_fields),
    ]

    result = CliRunner().invoke(app, ["config", "options"])

    assert result.exit_code == 0
    for name in expected:
        assert name in result.stdout


def test_options_marks_review_settings_as_project_only() -> None:
    project_only = "Only in the project"
    review_settings = len(ReviewSettings.model_fields)

    result = CliRunner().invoke(app, ["config", "options"])

    assert result.stdout.count(project_only) == review_settings
