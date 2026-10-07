import json
from enum import Enum, auto
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ConfigDict, RootModel
from safe_result import Err, Ok

from codetaster.delivery.console.configuration_loading import (
    load_configuration_or_exit,
)
from codetaster.delivery.console.conventions import codetaster_conventions
from codetaster.domain.application_services.initialise_configuration import (
    ConfigScope,
    ExistingFilePolicy,
    InitialisationError,
    InitialisationRequest,
    initialise_configuration,
)
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.conventions import (
    ConfigConventions,
)
from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ConfigFileExistsError,
    NoProjectRootError,
)
from codetaster.domain.domain_model.configuration.review_settings import (
    ProjectSettings,
)
from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.configuration.template import (
    SettingsTemplate,
    TemplateEntry,
)
from codetaster.domain.domain_model.filesystem import Location
from codetaster.infrastructure.config_file_store.local import LocalConfigFileStore
from codetaster.infrastructure.environment_variables.os_environment import (
    OsEnvironmentVariables,
)
from codetaster.infrastructure.repository_names.git_repository_names import (
    GitRepositoryNames,
)


class HelpText(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> HelpText:
        return HelpText("Write a config file.")


config_app = typer.Typer(no_args_is_help=True, help="Inspect and create configuration.")


def echo_configuration(configuration: Configuration) -> None:
    typer.echo("Loaded files:")
    for location in configuration.loaded_files.root:
        typer.echo(f"  {location.root}")
    if not configuration.loaded_files.root:
        typer.echo("  (none; using defaults)")

    api_token = configuration.secrets.api_token
    typer.echo("")
    typer.echo("Settings:")
    typer.echo(f"  log_format = {configuration.settings.log_format.value}")
    review = configuration.review
    typer.echo("Review:")
    if review is None:
        typer.echo("  (no [review] section in the project config)")
    else:
        typer.echo(f"  base_branch = {review.base_branch}")
        typer.echo(f"  base_probability = {review.base_probability.root}")
        typer.echo(f"  top_rated_percentage = {review.top_rated_percentage.root}")
        for rule in review.path_rules.root:
            typer.echo(f"  path_rules: {rule.pattern.root} = {rule.probability.root}")
    typer.echo("Secrets:")
    typer.echo(f"  api_token = {'(not set)' if api_token is None else '**********'}")


class SettingAvailability(Enum):
    EVERY_FILE = auto()
    PROJECT_ONLY = auto()


def describe_setting(
    entry: TemplateEntry, availability: SettingAvailability
) -> HelpText:
    name = (
        entry.name.root
        if entry.section is None
        else f"[{entry.section.root}] {entry.name.root}"
    )
    lines = [name]
    if entry.description is not None:
        lines.append(f"  {entry.description.root}")
    lines.append(
        "  Default: none, so it must be set"
        if entry.default is None
        else f"  Default: {json.dumps(entry.default.root)}"
    )
    if availability is SettingAvailability.PROJECT_ONLY:
        lines.append(
            f"  Only in the {ConfigScope.PROJECT} and "
            f"{ConfigScope.DEVELOPER_PROJECT} config files."
        )
    return HelpText("\n".join(lines))


@config_app.command("options")
def show_config_options() -> None:
    """List every setting a config file can contain, with its default."""
    everywhere = {
        (entry.section, entry.name)
        for entry in SettingsTemplate.from_settings_schema(Settings).root
    }
    entries = SettingsTemplate.from_settings_schema(ProjectSettings).root
    typer.echo(
        "\n\n".join(
            describe_setting(
                entry,
                SettingAvailability.EVERY_FILE
                if (entry.section, entry.name) in everywhere
                else SettingAvailability.PROJECT_ONLY,
            ).root
            for entry in entries
        )
    )


@config_app.command("show")
def show_config() -> None:
    """Print the effective configuration, with secrets redacted."""
    echo_configuration(load_configuration_or_exit(Location(Path.cwd())))


def config_init_help(conventions: ConfigConventions) -> HelpText:
    """Name every config location, so users know where files are written and read."""
    config_root = (
        f"${conventions.xdg_config_home_variable.root}/{conventions.app_directory.root}"
    )
    fallback_root = (
        f"~/{conventions.fallback_config_home.root}/{conventions.app_directory.root}"
    )
    developer_project_file = (
        f"<repository>{conventions.developer_project_file_suffix.root}"
    )
    return HelpText(
        "Write a config file listing every setting, commented out at its default.\n\n"
        f"The config root is {config_root}, or {fallback_root} if "
        f"{conventions.xdg_config_home_variable.root} is unset. Config is read "
        "from, later overriding earlier:\n\n"
        f"1. developer: <config root>/{conventions.developer_file.root}, "
        "for every repository.\n\n"
        f"2. project: {conventions.project_file.root}, found by searching from "
        "the current directory up to the git repository root. Written at the "
        "repository root.\n\n"
        f"3. developer-project: <config root>/{developer_project_file}, for one "
        "repository. <repository> is the name of the directory holding its main "
        "checkout, so every worktree shares the file.\n\n"
        "A \\[review] section replaces any earlier one as a whole.\n\n"
        f"Secrets are read from {conventions.api_token_variable.root}, "
        f"falling back to <config root>/{conventions.secrets_file.root}."
    )


@config_app.command("init", help=config_init_help(codetaster_conventions()).root)
def init_config(
    scope: Annotated[
        ConfigScope, typer.Option("--scope", help="Which config file to write.")
    ] = ConfigScope.PROJECT,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing config file.")
    ] = False,
) -> None:
    request = InitialisationRequest(
        home=Location(Path.home()),
        working_directory=Location(Path.cwd()),
        conventions=codetaster_conventions(),
        scope=scope,
        existing_file=ExistingFilePolicy.OVERWRITE
        if force
        else ExistingFilePolicy.REFUSE,
    )
    match initialise_configuration(
        request,
        LocalConfigFileStore(),
        OsEnvironmentVariables(),
        GitRepositoryNames(),
    ):
        case Ok(location):
            typer.echo(f"Wrote {location.root}")
        case Err(error):
            echo_initialisation_error(error)
            raise typer.Exit(code=1)


def echo_initialisation_error(error: InitialisationError) -> None:
    match error:
        case NoProjectRootError():
            typer.echo(
                f"Error: {error}. Run this inside a git repository, "
                f"or use --scope {ConfigScope.DEVELOPER} for the developer config.",
                err=True,
            )
        case ConfigFileExistsError():
            typer.echo(f"Error: {error}. Use --force to overwrite it.", err=True)
        case ConfigFileError():
            typer.echo(f"Error: could not write config file {error}", err=True)
        case _:
            typer.echo(
                f"Error: could not name the repository to find its config: {error}",
                err=True,
            )
