from pathlib import Path

from pydantic import SecretStr
from safe_result import Err, Ok

from codetaster.domain.application_services.load_configuration import (
    ConfigurationRequest,
    load_configuration,
)
from codetaster.domain.domain_model.configuration.secret_values import ApiToken
from codetaster.domain.domain_model.configuration.settings import LogFormat
from codetaster.domain.domain_model.environment import VariableName, VariableValue
from codetaster.domain.domain_model.filesystem import Location, Locations

# Domain tests use the fakes from infrastructure, which tach otherwise forbids.
from codetaster.infrastructure.config_file_reader.in_memory import (
    InMemoryConfigFileReader,
)
from codetaster.infrastructure.config_file_reader.toml_parsing import FileContent
from codetaster.infrastructure.environment_variables.in_memory import (
    InMemoryEnvironmentVariables,
)


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
    developer = Location(Path("/home/fake/.config/codetaster/config.toml"))
    project = Location(Path("/home/fake/repo/codetaster.toml"))
    files = InMemoryConfigFileReader(
        {
            developer: FileContent('log_format = "json"\n'),
            project: FileContent('log_format = "text"\n'),
        }
    )

    result = load_configuration(
        ConfigurationRequest.fake(), files, InMemoryEnvironmentVariables({})
    )

    match result:
        case Ok(configuration):
            assert configuration.settings.log_format == LogFormat.TEXT
            assert configuration.loaded_files == Locations((developer, project))
        case Err(error):
            raise error


def test_developer_config_survives_project_config_that_omits_the_field() -> None:
    developer = Location(Path("/home/fake/.config/codetaster/config.toml"))
    project = Location(Path("/home/fake/repo/codetaster.toml"))
    files = InMemoryConfigFileReader(
        {developer: FileContent('log_format = "json"\n'), project: FileContent("")}
    )

    result = load_configuration(
        ConfigurationRequest.fake(), files, InMemoryEnvironmentVariables({})
    )

    match result:
        case Ok(configuration):
            assert configuration.settings.log_format == LogFormat.JSON
        case Err(error):
            raise error


def test_xdg_config_home_replaces_dot_config() -> None:
    developer = Location(Path("/xdg/codetaster/config.toml"))
    files = InMemoryConfigFileReader({developer: FileContent('log_format = "json"\n')})
    environment = InMemoryEnvironmentVariables(
        {VariableName("XDG_CONFIG_HOME"): VariableValue("/xdg")}
    )

    result = load_configuration(ConfigurationRequest.fake(), files, environment)

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((developer,))
        case Err(error):
            raise error


def test_relative_xdg_config_home_is_ignored() -> None:
    developer = Location(Path("/home/fake/.config/codetaster/config.toml"))
    files = InMemoryConfigFileReader({developer: FileContent('log_format = "json"\n')})
    environment = InMemoryEnvironmentVariables(
        {VariableName("XDG_CONFIG_HOME"): VariableValue("relative")}
    )

    result = load_configuration(ConfigurationRequest.fake(), files, environment)

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((developer,))
        case Err(error):
            raise error


def test_project_config_is_found_in_a_parent_directory() -> None:
    project = Location(Path("/home/fake/repo/codetaster.toml"))
    files = InMemoryConfigFileReader(
        {project: FileContent('log_format = "json"\n')},
        [Location(Path("/home/fake/repo/.git"))],
    )
    request = ConfigurationRequest.fake().model_copy(
        update={"working_directory": Location(Path("/home/fake/repo/src/deep"))}
    )

    result = load_configuration(request, files, InMemoryEnvironmentVariables({}))

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((project,))
        case Err(error):
            raise error


def test_project_search_stops_at_the_repository_root() -> None:
    outside = Location(Path("/home/fake/codetaster.toml"))
    files = InMemoryConfigFileReader(
        {outside: FileContent('log_format = "json"\n')},
        [Location(Path("/home/fake/repo/.git"))],
    )

    result = load_configuration(
        ConfigurationRequest.fake(), files, InMemoryEnvironmentVariables({})
    )

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations(())
        case Err(error):
            raise error


def test_api_token_from_environment_overrides_secrets_file() -> None:
    secrets_file = Location(Path("/home/fake/.config/codetaster/secrets.toml"))
    files = InMemoryConfigFileReader(
        {secrets_file: FileContent('api_token = "from-file"\n')}
    )
    environment = InMemoryEnvironmentVariables(
        {VariableName("CODETASTER_API_TOKEN"): VariableValue("from-env")}
    )

    result = load_configuration(ConfigurationRequest.fake(), files, environment)

    match result:
        case Ok(configuration):
            assert configuration.secrets.api_token == ApiToken(SecretStr("from-env"))
            assert configuration.loaded_files == Locations((secrets_file,))
        case Err(error):
            raise error


def test_api_token_falls_back_to_secrets_file() -> None:
    secrets_file = Location(Path("/home/fake/.config/codetaster/secrets.toml"))
    files = InMemoryConfigFileReader(
        {secrets_file: FileContent('api_token = "from-file"\n')}
    )
    environment = InMemoryEnvironmentVariables(
        {VariableName("CODETASTER_API_TOKEN"): VariableValue("")}
    )

    result = load_configuration(ConfigurationRequest.fake(), files, environment)

    match result:
        case Ok(configuration):
            assert configuration.secrets.api_token == ApiToken(SecretStr("from-file"))
        case Err(error):
            raise error


def test_unknown_setting_is_an_error_naming_file_and_field() -> None:
    project = Location(Path("/home/fake/repo/codetaster.toml"))
    files = InMemoryConfigFileReader({project: FileContent('log_fromat = "json"\n')})

    result = load_configuration(
        ConfigurationRequest.fake(), files, InMemoryEnvironmentVariables({})
    )

    match result:
        case Err(error):
            assert error.location == project
            assert "log_fromat" in error.reason.root
        case Ok(configuration):
            raise AssertionError(configuration)


def test_malformed_developer_config_is_an_error() -> None:
    developer = Location(Path("/home/fake/.config/codetaster/config.toml"))
    files = InMemoryConfigFileReader({developer: FileContent("log_format = ")})

    result = load_configuration(
        ConfigurationRequest.fake(), files, InMemoryEnvironmentVariables({})
    )

    match result:
        case Err(error):
            assert error.location == developer
        case Ok(configuration):
            raise AssertionError(configuration)
