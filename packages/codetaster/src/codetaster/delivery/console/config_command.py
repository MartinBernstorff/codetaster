from pathlib import Path
from typing import Annotated

import typer
from safe_result import Err, Ok

from codetaster.domain.application_services.initialise_configuration import (
    ConfigScope,
    ExistingFilePolicy,
    InitialisationError,
    InitialisationRequest,
    initialise_configuration,
)
from codetaster.domain.application_services.load_configuration import (
    ConfigurationRequest,
    load_configuration,
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
from codetaster.domain.domain_model.environment import VariableName
from codetaster.domain.domain_model.filesystem import Location, PathName
from codetaster.infrastructure.config_file_reader.local import LocalConfigFileReader
from codetaster.infrastructure.config_file_writer.local import LocalConfigFileWriter
from codetaster.infrastructure.environment_variables.os_environment import (
    OsEnvironmentVariables,
)

config_app = typer.Typer(no_args_is_help=True, help="Inspect and create configuration.")


def codetaster_conventions() -> ConfigConventions:
    return ConfigConventions(
        app_directory=PathName("codetaster"),
        xdg_config_home_variable=VariableName("XDG_CONFIG_HOME"),
        fallback_config_home=PathName(".config"),
        developer_file=PathName("config.toml"),
        secrets_file=PathName("secrets.toml"),
        project_file=PathName("codetaster.toml"),
        repository_marker=PathName(".git"),
        api_token_variable=VariableName("CODETASTER_API_TOKEN"),
    )


def current_configuration_request() -> ConfigurationRequest:
    return ConfigurationRequest(
        home=Location(Path.home()),
        working_directory=Location(Path.cwd()),
        conventions=codetaster_conventions(),
    )


def load_current_configuration() -> Configuration:
    """Load configuration for the current process, or exit with a message."""
    match load_configuration(
        current_configuration_request(),
        LocalConfigFileReader(),
        OsEnvironmentVariables(),
    ):
        case Ok(configuration):
            return configuration
        case Err(error):
            typer.echo(f"Error: invalid config file {error}", err=True)
            raise typer.Exit(code=1)


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
    typer.echo("Secrets:")
    typer.echo(f"  api_token = {'(not set)' if api_token is None else '**********'}")


@config_app.command("show")
def show_config() -> None:
    """Print the effective configuration, with secrets redacted."""
    echo_configuration(load_current_configuration())


@config_app.command("init")
def init_config(
    developer: Annotated[
        bool,
        typer.Option(
            "--developer",
            help="Write the developer config in the user config directory, "
            "instead of the project config at the git repository root.",
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing config file.")
    ] = False,
) -> None:
    """Write a config file listing every setting, commented out at its default."""
    request = InitialisationRequest(
        home=Location(Path.home()),
        working_directory=Location(Path.cwd()),
        conventions=codetaster_conventions(),
        scope=ConfigScope.DEVELOPER if developer else ConfigScope.PROJECT,
        existing_file=ExistingFilePolicy.OVERWRITE
        if force
        else ExistingFilePolicy.REFUSE,
    )
    match initialise_configuration(
        request,
        LocalConfigFileReader(),
        LocalConfigFileWriter(),
        OsEnvironmentVariables(),
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
                "or use --developer for the developer config.",
                err=True,
            )
        case ConfigFileExistsError():
            typer.echo(f"Error: {error}. Use --force to overwrite it.", err=True)
        case ConfigFileError():
            typer.echo(f"Error: could not write config file {error}", err=True)
