import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from codetaster.delivery.console.app import app
from codetaster.domain.domain_model.configuration.settings import LogFormat, Settings
from codetaster.domain.domain_model.filesystem import Location, PathName
from codetaster.infrastructure.config_file_reader.toml_parsing import FileContent


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


def project_config(repository: Location) -> Location:
    return repository.joinpath(PathName("codetaster.toml"))


def developer_config(config_home: Location) -> Location:
    return config_home.joinpath(PathName("codetaster")).joinpath(
        PathName("config.toml")
    )


def uncomment_settings(content: FileContent) -> FileContent:
    """Uncomment each assignment, including the lines of a multi-line value.

    An assignment runs from its `# <name> = ` line to the end of its block.
    """
    assignments = tuple(f"# {name} = " for name in Settings.model_fields)
    lines: list[str] = []
    in_assignment = False
    for line in content.root.splitlines():
        in_assignment = line.startswith(assignments) or (in_assignment and line != "")
        lines.append(line.removeprefix("# ") if in_assignment else line)
    return FileContent("\n".join(lines))


def test_shows_effective_config_and_loaded_files(
    repository: Location, config_home: Location
) -> None:
    success_exit_code = 0
    developer_format = LogFormat.TEXT
    project_format = LogFormat.JSON
    api_token = "s3cret"
    redacted = "**********"
    developer = developer_config(config_home).root
    _ = developer.write_text(f'log_format = "{developer_format}"\n')
    project = project_config(repository).root
    _ = project.write_text(f'log_format = "{project_format}"\n')

    result = CliRunner().invoke(
        app,
        ["config", "show"],
        env={
            "XDG_CONFIG_HOME": str(config_home.root),
            "CODETASTER_API_TOKEN": api_token,
        },
    )

    assert result.exit_code == success_exit_code, result.output
    assert str(developer) in result.output
    assert str(project) in result.output
    assert f"log_format = {project_format}" in result.output
    assert f"api_token = {redacted}" in result.output
    assert api_token not in result.output


@pytest.mark.usefixtures("repository")
def test_reports_defaults_and_unset_secret(config_home: Location) -> None:
    success_exit_code = 0
    no_files_loaded = "(none; using defaults)"
    unset = "(not set)"
    default_format = Settings().log_format

    result = CliRunner().invoke(
        app,
        ["config", "show"],
        env={"XDG_CONFIG_HOME": str(config_home.root), "CODETASTER_API_TOKEN": None},
    )

    assert result.exit_code == success_exit_code, result.output
    assert no_files_loaded in result.output
    assert f"log_format = {default_format}" in result.output
    assert f"api_token = {unset}" in result.output


def test_malformed_config_exits_nonzero_naming_the_file(
    repository: Location, config_home: Location
) -> None:
    failure_exit_code = 1
    project = project_config(repository).root
    _ = project.write_text("log_format = \n")

    result = CliRunner().invoke(
        app, ["config", "show"], env={"XDG_CONFIG_HOME": str(config_home.root)}
    )

    assert result.exit_code == failure_exit_code
    assert str(project) in result.output


def test_init_writes_project_config_at_the_repository_root(
    repository: Location, config_home: Location
) -> None:
    success_exit_code = 0
    project = project_config(repository).root

    result = CliRunner().invoke(
        app, ["config", "init"], env={"XDG_CONFIG_HOME": str(config_home.root)}
    )

    assert result.exit_code == success_exit_code, result.output
    assert str(project) in result.output
    assert project.is_file()


def test_init_comments_out_every_setting_at_its_default(
    repository: Location, config_home: Location
) -> None:
    project = project_config(repository).root
    defaults = Settings()

    _ = CliRunner().invoke(
        app, ["config", "init"], env={"XDG_CONFIG_HOME": str(config_home.root)}
    )

    text = project.read_text()
    assert tomllib.loads(text) == {}
    uncommented = tomllib.loads(uncomment_settings(FileContent(text)).root)
    assert uncommented.keys() == Settings.model_fields.keys()
    assert Settings.model_validate(uncommented) == defaults


def test_initialised_config_loads(repository: Location, config_home: Location) -> None:
    success_exit_code = 0
    project = project_config(repository).root
    env = {"XDG_CONFIG_HOME": str(config_home.root)}
    _ = CliRunner().invoke(app, ["config", "init"], env=env)

    as_written = CliRunner().invoke(app, ["config", "show"], env=env)
    _ = project.write_text(uncomment_settings(FileContent(project.read_text())).root)
    uncommented = CliRunner().invoke(app, ["config", "show"], env=env)

    assert as_written.exit_code == success_exit_code, as_written.output
    assert str(project) in as_written.output
    assert uncommented.exit_code == success_exit_code, uncommented.output


def test_init_refuses_to_overwrite_without_force(
    repository: Location, config_home: Location
) -> None:
    failure_exit_code = 1
    project = project_config(repository).root
    existing = 'log_format = "json"\n'
    _ = project.write_text(existing)
    force_flag = "--force"

    result = CliRunner().invoke(
        app, ["config", "init"], env={"XDG_CONFIG_HOME": str(config_home.root)}
    )

    assert result.exit_code == failure_exit_code
    assert str(project) in result.output
    assert force_flag in result.output
    assert project.read_text() == existing


def test_init_with_force_overwrites(
    repository: Location, config_home: Location
) -> None:
    success_exit_code = 0
    project = project_config(repository).root
    existing = 'log_format = "json"\n'
    _ = project.write_text(existing)

    result = CliRunner().invoke(
        app,
        ["config", "init", "--force"],
        env={"XDG_CONFIG_HOME": str(config_home.root)},
    )

    assert result.exit_code == success_exit_code, result.output
    assert project.read_text() != existing


def test_init_outside_a_repository_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config_home: Location
) -> None:
    failure_exit_code = 1
    monkeypatch.chdir(tmp_path)
    expected_message = "no project root (git repository)"

    result = CliRunner().invoke(
        app, ["config", "init"], env={"XDG_CONFIG_HOME": str(config_home.root)}
    )

    assert result.exit_code == failure_exit_code
    assert expected_message in result.output


@pytest.mark.usefixtures("repository")
def test_init_developer_writes_under_xdg_config_home(tmp_path: Path) -> None:
    success_exit_code = 0
    config_home = Location(tmp_path / "fresh-xdg")
    developer = developer_config(config_home).root

    result = CliRunner().invoke(
        app,
        ["config", "init", "--developer"],
        env={"XDG_CONFIG_HOME": str(config_home.root)},
    )

    assert result.exit_code == success_exit_code, result.output
    assert str(developer) in result.output
    assert developer.is_file()


@pytest.mark.usefixtures("repository")
def test_init_developer_falls_back_to_dot_config_in_home(tmp_path: Path) -> None:
    success_exit_code = 0
    home = tmp_path / "home"
    developer = home / ".config" / "codetaster" / "config.toml"

    result = CliRunner().invoke(
        app,
        ["config", "init", "--developer"],
        env={"HOME": str(home), "XDG_CONFIG_HOME": None},
    )

    assert result.exit_code == success_exit_code, result.output
    assert developer.is_file()
