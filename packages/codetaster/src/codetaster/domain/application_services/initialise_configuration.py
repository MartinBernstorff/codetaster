from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from safe_result import Err, Ok, Result

from codetaster.domain.application_services.config_locations import (
    find_repository_root,
    resolve_config_root,
)
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
from codetaster.domain.domain_model.configuration.template import SettingsTemplate
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.secondary_ports.config_file_store import ConfigFileStore
from codetaster.domain.secondary_ports.environment_variables import (
    EnvironmentVariables,
)


class ConfigScope(StrEnum):
    """Which config file to write."""

    PROJECT = "project"
    DEVELOPER = "developer"


class ExistingFilePolicy(StrEnum):
    REFUSE = "refuse"
    OVERWRITE = "overwrite"


class InitialisationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    home: Location
    working_directory: Location
    conventions: ConfigConventions
    scope: ConfigScope
    existing_file: ExistingFilePolicy

    @staticmethod
    def fake() -> InitialisationRequest:
        return InitialisationRequest(
            home=Location(Path("/home/fake")),
            working_directory=Location(Path("/home/fake/repo")),
            conventions=ConfigConventions.fake(),
            scope=ConfigScope.PROJECT,
            existing_file=ExistingFilePolicy.REFUSE,
        )


type InitialisationError = NoProjectRootError | ConfigFileExistsError | ConfigFileError


def initialise_configuration(
    request: InitialisationRequest,
    files: ConfigFileStore,
    environment: EnvironmentVariables,
) -> Result[Location, InitialisationError]:
    """Write a config file listing every setting, commented out at its default.

    The project file goes in the repository root; the developer file in the
    config root. Returns where the file was written.
    """
    target = config_file_for_scope(request, files, environment)
    if isinstance(target, Err):
        return target
    location = target.value
    if request.existing_file is ExistingFilePolicy.REFUSE and files.exists(location):
        return Err(ConfigFileExistsError(location))
    written = files.write_template(
        location,
        SettingsTemplate.from_settings_schema(settings_model_for(request.scope)),
    )
    if isinstance(written, Err):
        return written
    return Ok(location)


def settings_model_for(scope: ConfigScope) -> type[Settings]:
    """Only the project config may contain project-only sections, like `[review]`."""
    match scope:
        case ConfigScope.DEVELOPER:
            return Settings
        case ConfigScope.PROJECT:
            return ProjectSettings


def config_file_for_scope(
    request: InitialisationRequest,
    files: ConfigFileStore,
    environment: EnvironmentVariables,
) -> Result[Location, NoProjectRootError]:
    conventions = request.conventions
    match request.scope:
        case ConfigScope.DEVELOPER:
            config_root = resolve_config_root(request.home, conventions, environment)
            return Ok(config_root.joinpath(conventions.developer_file))
        case ConfigScope.PROJECT:
            repository_root = find_repository_root(
                request.working_directory, conventions, files
            )
            if repository_root is None:
                return Err(NoProjectRootError(request.working_directory))
            return Ok(repository_root.joinpath(conventions.project_file))
