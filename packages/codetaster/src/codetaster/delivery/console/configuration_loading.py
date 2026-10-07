"""Loading configuration for a command, shared by the commands that need it."""

from pathlib import Path

import typer
from safe_result import Err

from codetaster.delivery.console.conventions import codetaster_conventions
from codetaster.domain.application_services.load_configuration import (
    ConfigurationRequest,
    load_configuration,
)
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.errors import ConfigFileError
from codetaster.domain.domain_model.filesystem import Location
from codetaster.infrastructure.config_file_store.local import LocalConfigFileStore
from codetaster.infrastructure.environment_variables.os_environment import (
    OsEnvironmentVariables,
)
from codetaster.infrastructure.repository_names.git_repository_names import (
    GitRepositoryNames,
)


def load_configuration_or_exit(working_directory: Location) -> Configuration:
    """The configuration for `working_directory`, or exit with a message."""
    configuration = load_configuration(
        ConfigurationRequest(
            home=Location(Path.home()),
            working_directory=working_directory,
            conventions=codetaster_conventions(),
        ),
        LocalConfigFileStore(),
        OsEnvironmentVariables(),
        GitRepositoryNames(),
    )
    if isinstance(configuration, Err):
        match configuration.error:
            case ConfigFileError() as error:
                typer.echo(f"Error: invalid config file {error}", err=True)
            case error:
                typer.echo(
                    f"Error: could not name the repository to find its config: {error}",
                    err=True,
                )
        raise typer.Exit(code=1)
    return configuration.value
