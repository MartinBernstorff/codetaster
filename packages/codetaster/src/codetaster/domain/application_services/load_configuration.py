from pathlib import Path

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError
from safe_result import Err, Ok, Result

from codetaster.domain.application_services.config_locations import (
    resolve_config_root,
)
from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.conventions import (
    ConfigConventions,
)
from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ErrorReason,
)
from codetaster.domain.domain_model.configuration.review_settings import (
    ProjectSettings,
)
from codetaster.domain.domain_model.configuration.secret_values import (
    ApiToken,
    Secrets,
)
from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.filesystem import Location, Locations
from codetaster.domain.secondary_ports.config_file_store import ConfigFileStore
from codetaster.domain.secondary_ports.environment_variables import (
    EnvironmentVariables,
)


class ConfigurationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    home: Location
    working_directory: Location
    conventions: ConfigConventions

    @staticmethod
    def fake() -> ConfigurationRequest:
        return ConfigurationRequest(
            home=Location(Path("/home/fake")),
            working_directory=Location(Path("/home/fake/repo")),
            conventions=ConfigConventions.fake(),
        )


def load_configuration(
    request: ConfigurationRequest,
    files: ConfigFileStore,
    environment: EnvironmentVariables,
) -> Result[Configuration, ConfigFileError]:
    """Defaults, overridden by developer config, overridden by project config.

    Secrets come from environment variables, falling back to the secrets file.
    """
    conventions = request.conventions
    config_root = resolve_config_root(request.home, conventions, environment)

    settings = Settings()
    loaded: list[Location] = []
    developer_location = config_root.joinpath(conventions.developer_file)
    developer = read_developer_settings(developer_location, files)
    if isinstance(developer, Err):
        return developer
    if developer.value is not None:
        settings = settings.overridden_by(developer.value)
        loaded.append(developer_location)

    review = None
    project_location = find_project_config(
        request.working_directory, conventions, files
    )
    if project_location is not None:
        project = read_model(ProjectSettings, project_location, files)
        if isinstance(project, Err):
            return project
        if project.value is not None:
            settings = settings.overridden_by(project.value)
            review = project.value.review
            loaded.append(project_location)

    secrets_location = config_root.joinpath(conventions.secrets_file)
    file_secrets = read_model(Secrets, secrets_location, files)
    if isinstance(file_secrets, Err):
        return file_secrets
    if file_secrets.value is not None:
        loaded.append(secrets_location)

    return Ok(
        Configuration(
            settings=settings,
            secrets=secrets_with_environment_overrides(
                file_secrets.value or Secrets(), conventions, environment
            ),
            review=review,
            loaded_files=Locations(tuple(loaded)),
        )
    )


def read_developer_settings(
    location: Location, files: ConfigFileStore
) -> Result[Settings | None, ConfigFileError]:
    """Like `read_model`, but names a project-only section if it is present."""
    read = files.read_document(location)
    if isinstance(read, Err):
        return read
    if read.value is None:
        return Ok(None)
    project_only = sorted(
        ProjectSettings.model_fields.keys() - Settings.model_fields.keys()
    )
    for section in project_only:
        if section in read.value.root:
            return Err(
                ConfigFileError(
                    location,
                    ErrorReason(
                        f"[{section}] is project-only; move it to the project config"
                    ),
                )
            )
    return validate_document(Settings, read.value, location)


def find_project_config(
    start: Location, conventions: ConfigConventions, files: ConfigFileStore
) -> Location | None:
    """Search `start` and its parents, up to and including the repository root."""
    for directory in start.lineage().root:
        candidate = directory.joinpath(conventions.project_file)
        if files.exists(candidate):
            return candidate
        if files.exists(directory.joinpath(conventions.repository_marker)):
            return None
    return None


def read_model[M: BaseModel](
    model: type[M], location: Location, files: ConfigFileStore
) -> Result[M | None, ConfigFileError]:
    read = files.read_document(location)
    if isinstance(read, Err):
        return read
    if read.value is None:
        return Ok(None)
    return validate_document(model, read.value, location)


def validate_document[M: BaseModel](
    model: type[M], document: ConfigDocument, location: Location
) -> Result[M, ConfigFileError]:
    try:
        validated = model.model_validate(document.root)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
            for problem in error.errors()
        )
        return Err(ConfigFileError(location, ErrorReason(problems)))
    return Ok(validated)


def secrets_with_environment_overrides(
    secrets: Secrets, conventions: ConfigConventions, environment: EnvironmentVariables
) -> Secrets:
    api_token = environment.value_of(conventions.api_token_variable)
    if api_token is None or api_token.is_blank():
        return secrets
    return secrets.model_copy(update={"api_token": ApiToken(SecretStr(api_token.root))})
