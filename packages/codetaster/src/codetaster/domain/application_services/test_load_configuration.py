from pathlib import Path

from pydantic import SecretStr
from safe_result import Err, Ok

from codetaster.domain.application_services.load_configuration import (
    ConfigurationRequest,
    load_configuration,
)
from codetaster.domain.domain_model.configuration.secret_values import ApiToken
from codetaster.domain.domain_model.configuration.settings import LogFormat
from codetaster.domain.domain_model.environment import VariableValue
from codetaster.domain.domain_model.filesystem import Location, Locations, PathName

# Domain tests use the fakes from infrastructure, which tach otherwise forbids.
from codetaster.infrastructure.config_file_reader.in_memory import (
    InMemoryConfigFileReader,
)
from codetaster.infrastructure.config_file_reader.toml_parsing import FileContent
from codetaster.infrastructure.environment_variables.in_memory import (
    InMemoryEnvironmentVariables,
)


def default_config_directory(request: ConfigurationRequest) -> Location:
    conventions = request.conventions
    return request.home.joinpath(conventions.fallback_config_home).joinpath(
        conventions.app_directory
    )


def developer_config_location(request: ConfigurationRequest) -> Location:
    return default_config_directory(request).joinpath(
        request.conventions.developer_file
    )


def secrets_file_location(request: ConfigurationRequest) -> Location:
    return default_config_directory(request).joinpath(request.conventions.secrets_file)


def project_config_location(request: ConfigurationRequest) -> Location:
    return request.working_directory.joinpath(request.conventions.project_file)


def repository_marker_location(request: ConfigurationRequest) -> Location:
    return request.working_directory.joinpath(request.conventions.repository_marker)


def log_format_setting(log_format: LogFormat) -> FileContent:
    return FileContent(f'log_format = "{log_format}"\n')


def api_token_setting(token: ApiToken) -> FileContent:
    return FileContent(f'api_token = "{token.root.get_secret_value()}"\n')


def test_defaults_when_no_files_exist() -> None:
    result = load_configuration(
        ConfigurationRequest.fake(),
        InMemoryConfigFileReader({}),
        InMemoryEnvironmentVariables({}),
    )

    match result:
        case Ok(configuration):
            assert configuration.settings.log_format == LogFormat.TEXT
            assert configuration.secrets.api_token is None
            assert configuration.loaded_files == Locations(())
        case Err(error):
            raise error


def test_project_config_overrides_developer_config() -> None:
    request = ConfigurationRequest.fake()
    developer = developer_config_location(request)
    project = project_config_location(request)
    project_format = LogFormat.TEXT
    files = InMemoryConfigFileReader(
        {
            developer: log_format_setting(LogFormat.JSON),
            project: log_format_setting(project_format),
        }
    )

    result = load_configuration(request, files, InMemoryEnvironmentVariables({}))

    match result:
        case Ok(configuration):
            assert configuration.settings.log_format == project_format
            assert configuration.loaded_files == Locations((developer, project))
        case Err(error):
            raise error


def test_developer_config_survives_project_config_that_omits_the_field() -> None:
    request = ConfigurationRequest.fake()
    developer_format = LogFormat.JSON
    files = InMemoryConfigFileReader(
        {
            developer_config_location(request): log_format_setting(developer_format),
            project_config_location(request): FileContent(""),
        }
    )

    result = load_configuration(request, files, InMemoryEnvironmentVariables({}))

    match result:
        case Ok(configuration):
            assert configuration.settings.log_format == developer_format
        case Err(error):
            raise error


def test_xdg_config_home_replaces_dot_config() -> None:
    request = ConfigurationRequest.fake()
    conventions = request.conventions
    xdg_config_home = Location(Path("/xdg"))
    developer = xdg_config_home.joinpath(conventions.app_directory).joinpath(
        conventions.developer_file
    )
    files = InMemoryConfigFileReader({developer: FileContent.fake()})
    environment = InMemoryEnvironmentVariables(
        {conventions.xdg_config_home_variable: VariableValue(str(xdg_config_home.root))}
    )

    result = load_configuration(request, files, environment)

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((developer,))
        case Err(error):
            raise error


def test_relative_xdg_config_home_is_ignored() -> None:
    request = ConfigurationRequest.fake()
    developer = developer_config_location(request)
    files = InMemoryConfigFileReader({developer: FileContent.fake()})
    environment = InMemoryEnvironmentVariables(
        {request.conventions.xdg_config_home_variable: VariableValue("relative")}
    )

    result = load_configuration(request, files, environment)

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((developer,))
        case Err(error):
            raise error


def test_project_config_is_found_in_a_parent_directory() -> None:
    repository_request = ConfigurationRequest.fake()
    project = project_config_location(repository_request)
    files = InMemoryConfigFileReader(
        {project: FileContent.fake()},
        [repository_marker_location(repository_request)],
    )
    subdirectory = repository_request.working_directory.joinpath(PathName("src"))
    request = repository_request.model_copy(update={"working_directory": subdirectory})

    result = load_configuration(request, files, InMemoryEnvironmentVariables({}))

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((project,))
        case Err(error):
            raise error


def test_project_search_stops_at_the_repository_root() -> None:
    request = ConfigurationRequest.fake()
    above_repository = Location(request.working_directory.root.parent)
    files = InMemoryConfigFileReader(
        {
            above_repository.joinpath(
                request.conventions.project_file
            ): FileContent.fake()
        },
        [repository_marker_location(request)],
    )

    result = load_configuration(request, files, InMemoryEnvironmentVariables({}))

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations(())
        case Err(error):
            raise error


def test_api_token_from_environment_overrides_secrets_file() -> None:
    request = ConfigurationRequest.fake()
    secrets_file = secrets_file_location(request)
    environment_token = VariableValue("from-env")
    files = InMemoryConfigFileReader(
        {secrets_file: api_token_setting(ApiToken(SecretStr("from-file")))}
    )
    environment = InMemoryEnvironmentVariables(
        {request.conventions.api_token_variable: environment_token}
    )

    result = load_configuration(request, files, environment)

    match result:
        case Ok(configuration):
            assert configuration.secrets.api_token == ApiToken(
                SecretStr(environment_token.root)
            )
            assert configuration.loaded_files == Locations((secrets_file,))
        case Err(error):
            raise error


def test_api_token_falls_back_to_secrets_file() -> None:
    request = ConfigurationRequest.fake()
    file_token = ApiToken.fake()
    files = InMemoryConfigFileReader(
        {secrets_file_location(request): api_token_setting(file_token)}
    )
    environment = InMemoryEnvironmentVariables(
        {request.conventions.api_token_variable: VariableValue("")}
    )

    result = load_configuration(request, files, environment)

    match result:
        case Ok(configuration):
            assert configuration.secrets.api_token == file_token
        case Err(error):
            raise error


def test_unknown_setting_is_an_error_naming_file_and_field() -> None:
    request = ConfigurationRequest.fake()
    project = project_config_location(request)
    unknown_field = "log_fromat"
    files = InMemoryConfigFileReader(
        {project: FileContent(f'{unknown_field} = "json"\n')}
    )

    result = load_configuration(request, files, InMemoryEnvironmentVariables({}))

    match result:
        case Err(error):
            assert error.location == project
            assert unknown_field in error.reason.root
        case Ok(configuration):
            raise AssertionError(configuration)


def test_malformed_developer_config_is_an_error() -> None:
    request = ConfigurationRequest.fake()
    developer = developer_config_location(request)
    files = InMemoryConfigFileReader({developer: FileContent("log_format = ")})

    result = load_configuration(request, files, InMemoryEnvironmentVariables({}))

    match result:
        case Err(error):
            assert error.location == developer
        case Ok(configuration):
            raise AssertionError(configuration)
