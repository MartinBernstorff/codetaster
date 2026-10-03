from pathlib import Path

import pytest
from typer.testing import CliRunner

from codetaster.delivery.console.app import app
from codetaster.domain.domain_model.filesystem import Location, PathName


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Location:
    repository = tmp_path / "repo"
    (repository / ".git").mkdir(parents=True)
    (repository / "src").mkdir()
    monkeypatch.chdir(repository / "src")
    return Location(repository)


@pytest.fixture
def config_home(tmp_path: Path) -> Location:
    config_home = tmp_path / "xdg"
    (config_home / "codetaster").mkdir(parents=True)
    return Location(config_home)


def test_shows_effective_config_and_loaded_files(
    repository: Location, config_home: Location
) -> None:
    developer = config_home.root / "codetaster" / "config.toml"
    _ = developer.write_text('log_format = "text"\n')
    project = repository.joinpath(PathName("codetaster.toml")).root
    _ = project.write_text('log_format = "json"\n')

    result = CliRunner().invoke(
        app,
        ["config", "show"],
        env={
            "XDG_CONFIG_HOME": str(config_home.root),
            "CODETASTER_API_TOKEN": "s3cret",
        },
    )

    assert result.exit_code == 0, result.output
    assert str(developer) in result.output
    assert str(project) in result.output
    assert "log_format = json" in result.output
    assert "api_token = **********" in result.output
    assert "s3cret" not in result.output


@pytest.mark.usefixtures("repository")
def test_reports_defaults_and_unset_secret(config_home: Location) -> None:
    result = CliRunner().invoke(
        app,
        ["config", "show"],
        env={"XDG_CONFIG_HOME": str(config_home.root), "CODETASTER_API_TOKEN": None},
    )

    assert result.exit_code == 0, result.output
    assert "(none; using defaults)" in result.output
    assert "log_format = text" in result.output
    assert "api_token = (not set)" in result.output


def test_malformed_config_exits_nonzero_naming_the_file(
    repository: Location, config_home: Location
) -> None:
    project = repository.joinpath(PathName("codetaster.toml")).root
    _ = project.write_text("log_format = \n")

    result = CliRunner().invoke(
        app, ["config", "show"], env={"XDG_CONFIG_HOME": str(config_home.root)}
    )

    assert result.exit_code == 1
    assert str(project) in result.output
