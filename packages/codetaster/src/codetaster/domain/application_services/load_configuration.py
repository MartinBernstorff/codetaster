from pathlib import Path

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.configuration.configuration import Configuration
from codetaster.domain.domain_model.configuration.conventions import (
    ConfigConventions,
)
from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ErrorReason,
)
from codetaster.domain.domain_model.configuration.secret_values import (
    ApiToken,
    Secrets,
)
from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.filesystem import Location, Locations
from codetaster.domain.secondary_ports.config_file_reader import ConfigFileReader
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
    files: ConfigFileReader,
    environment: EnvironmentVariables,
) -> Result[Configuration, ConfigFileError]:
    """Defaults, overridden by developer config, overridden by project config.

    Secrets come from environment variables, falling back to the secrets file.
    """
    conventions = request.conventions
    config_root = resolve_config_root(request, environment)
    candidates = [
        config_root.joinpath(conventions.developer_file),
        find_project_config(request.working_directory, conventions, files),
    ]

    settings = Settings()
    loaded: list[Location] = []
    for location in candidates:
        if location is None:
            continue
        read = read_model(Settings, location, files)
        if isinstance(read, Err):
            return read
        if read.value is not None:
            settings = settings.overridden_by(read.value)
            loaded.append(location)

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
            loaded_files=Locations(tuple(loaded)),
        )
    )


def resolve_config_root(
    request: ConfigurationRequest, environment: EnvironmentVariables
) -> Location:
    """`$XDG_CONFIG_HOME/<app>`, or `~/.config/<app>` if that is unset or relative."""
    conventions = request.conventions
    xdg_config_home = environment.value_of(conventions.xdg_config_home_variable)
    base = (
        Location(Path(xdg_config_home.root))
        if xdg_config_home is not None and Path(xdg_config_home.root).is_absolute()
        else request.home.joinpath(conventions.fallback_config_home)
    )
    return base.joinpath(conventions.app_directory)


def find_project_config(
    start: Location, conventions: ConfigConventions, files: ConfigFileReader
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
    model: type[M], location: Location, files: ConfigFileReader
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
