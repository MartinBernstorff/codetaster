from pathlib import Path

from pydantic import SecretStr
from safe_result import Err, Ok

from codetaster.domain.application_services.load_configuration import (
    ConfigurationRequest,
    load_configuration,
)
from codetaster.domain.domain_model.checkout import CheckoutPath, RepositoryName
from codetaster.domain.domain_model.configuration.errors import ConfigFileError
from codetaster.domain.domain_model.configuration.review_settings import ReviewSettings
from codetaster.domain.domain_model.configuration.secret_values import ApiToken
from codetaster.domain.domain_model.configuration.settings import LogFormat
from codetaster.domain.domain_model.environment import VariableValue
from codetaster.domain.domain_model.filesystem import Location, Locations, PathName
from codetaster.domain.domain_model.review.probability import Probability

# Domain tests use the fakes from infrastructure, which tach otherwise forbids.
from codetaster.infrastructure.config_file_store.in_memory import (
    InMemoryConfigFileStore,
)
from codetaster.infrastructure.config_file_store.toml_parsing import FileContent
from codetaster.infrastructure.environment_variables.in_memory import (
    InMemoryEnvironmentVariables,
)
from codetaster.infrastructure.repository_names.fake_repository_names import (
    FakeRepositoryNames,
)


def repository_names() -> FakeRepositoryNames:
    """Names the repository at the fake request's working directory."""
    repository = CheckoutPath(ConfigurationRequest.fake().working_directory.root)
    return FakeRepositoryNames({repository: RepositoryName.fake()})


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
        InMemoryConfigFileStore({}),
        InMemoryEnvironmentVariables({}),
        repository_names(),
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
    files = InMemoryConfigFileStore(
        {
            developer: log_format_setting(LogFormat.JSON),
            project: log_format_setting(project_format),
        }
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Ok(configuration):
            assert configuration.settings.log_format == project_format
            assert configuration.loaded_files == Locations((developer, project))
        case Err(error):
            raise error


def test_developer_config_survives_project_config_that_omits_the_field() -> None:
    request = ConfigurationRequest.fake()
    developer_format = LogFormat.JSON
    files = InMemoryConfigFileStore(
        {
            developer_config_location(request): log_format_setting(developer_format),
            project_config_location(request): FileContent(""),
        }
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

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
    files = InMemoryConfigFileStore({developer: FileContent.fake()})
    environment = InMemoryEnvironmentVariables(
        {conventions.xdg_config_home_variable: VariableValue(str(xdg_config_home.root))}
    )

    result = load_configuration(request, files, environment, repository_names())

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((developer,))
        case Err(error):
            raise error


def test_relative_xdg_config_home_is_ignored() -> None:
    request = ConfigurationRequest.fake()
    developer = developer_config_location(request)
    files = InMemoryConfigFileStore({developer: FileContent.fake()})
    environment = InMemoryEnvironmentVariables(
        {request.conventions.xdg_config_home_variable: VariableValue("relative")}
    )

    result = load_configuration(request, files, environment, repository_names())

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((developer,))
        case Err(error):
            raise error


def test_project_config_is_found_in_a_parent_directory() -> None:
    repository_request = ConfigurationRequest.fake()
    project = project_config_location(repository_request)
    files = InMemoryConfigFileStore(
        {project: FileContent.fake()},
        [repository_marker_location(repository_request)],
    )
    subdirectory = repository_request.working_directory.joinpath(PathName("src"))
    request = repository_request.model_copy(update={"working_directory": subdirectory})

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations((project,))
        case Err(error):
            raise error


def test_project_search_stops_at_the_repository_root() -> None:
    request = ConfigurationRequest.fake()
    above_repository = Location(request.working_directory.root.parent)
    files = InMemoryConfigFileStore(
        {
            above_repository.joinpath(
                request.conventions.project_file
            ): FileContent.fake()
        },
        [repository_marker_location(request)],
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Ok(configuration):
            assert configuration.loaded_files == Locations(())
        case Err(error):
            raise error


def test_api_token_from_environment_overrides_secrets_file() -> None:
    request = ConfigurationRequest.fake()
    secrets_file = secrets_file_location(request)
    environment_token = VariableValue("from-env")
    files = InMemoryConfigFileStore(
        {secrets_file: api_token_setting(ApiToken(SecretStr("from-file")))}
    )
    environment = InMemoryEnvironmentVariables(
        {request.conventions.api_token_variable: environment_token}
    )

    result = load_configuration(request, files, environment, repository_names())

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
    files = InMemoryConfigFileStore(
        {secrets_file_location(request): api_token_setting(file_token)}
    )
    environment = InMemoryEnvironmentVariables(
        {request.conventions.api_token_variable: VariableValue("")}
    )

    result = load_configuration(request, files, environment, repository_names())

    match result:
        case Ok(configuration):
            assert configuration.secrets.api_token == file_token
        case Err(error):
            raise error


def test_unknown_setting_is_an_error_naming_file_and_field() -> None:
    request = ConfigurationRequest.fake()
    project = project_config_location(request)
    unknown_field = "log_fromat"
    files = InMemoryConfigFileStore(
        {project: FileContent(f'{unknown_field} = "json"\n')}
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Err(ConfigFileError() as error):
            assert error.location == project
            assert unknown_field in error.reason.root
        case _:
            raise AssertionError(result)


def test_malformed_developer_config_is_an_error() -> None:
    request = ConfigurationRequest.fake()
    developer = developer_config_location(request)
    files = InMemoryConfigFileStore({developer: FileContent("log_format = ")})

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Err(ConfigFileError() as error):
            assert error.location == developer
        case _:
            raise AssertionError(result)


def review_section(settings: ReviewSettings) -> FileContent:
    return FileContent(
        "[review]\n"
        f'base_branch = "{settings.base_branch}"\n'
        f"base_probability = {settings.base_probability.root}\n"
    )


def test_review_settings_come_from_the_project_config() -> None:
    request = ConfigurationRequest.fake()
    review = ReviewSettings.fake()
    files = InMemoryConfigFileStore(
        {project_config_location(request): review_section(review)}
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Ok(configuration):
            assert configuration.review == review
        case Err(error):
            raise error


def test_review_settings_are_absent_without_a_review_section() -> None:
    request = ConfigurationRequest.fake()
    files = InMemoryConfigFileStore({project_config_location(request): FileContent("")})

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Ok(configuration):
            assert configuration.review is None
        case Err(error):
            raise error


def test_review_section_in_developer_config_is_an_error() -> None:
    request = ConfigurationRequest.fake()
    developer = developer_config_location(request)
    section = "[review]"
    files = InMemoryConfigFileStore({developer: review_section(ReviewSettings.fake())})

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Err(ConfigFileError() as error):
            assert error.location == developer
            assert section in error.reason.root
        case _:
            raise AssertionError(result)


def test_base_probability_above_one_is_an_error() -> None:
    request = ConfigurationRequest.fake()
    project = project_config_location(request)
    field = "base_probability"
    files = InMemoryConfigFileStore(
        {project: FileContent(f'[review]\nbase_branch = "main"\n{field} = 1.5\n')}
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Err(ConfigFileError() as error):
            assert error.location == project
            assert field in error.reason.root
        case _:
            raise AssertionError(result)


def developer_project_config_location(request: ConfigurationRequest) -> Location:
    return default_config_directory(request).joinpath(
        request.conventions.developer_project_file(RepositoryName.fake())
    )


def test_developer_project_config_overrides_project_config() -> None:
    request = ConfigurationRequest.fake()
    project = project_config_location(request)
    developer_project = developer_project_config_location(request)
    developer_project_format = LogFormat.JSON
    files = InMemoryConfigFileStore(
        {
            project: log_format_setting(LogFormat.TEXT),
            developer_project: log_format_setting(developer_project_format),
        },
        [repository_marker_location(request)],
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Ok(configuration):
            assert configuration.settings.log_format == developer_project_format
            assert configuration.loaded_files == Locations((project, developer_project))
        case Err(error):
            raise error


def test_review_section_in_developer_project_config_replaces_the_projects() -> None:
    request = ConfigurationRequest.fake()
    developer_review = ReviewSettings.fake().model_copy(
        update={"base_probability": Probability(0.75)}
    )
    files = InMemoryConfigFileStore(
        {
            project_config_location(request): review_section(ReviewSettings.fake()),
            developer_project_config_location(request): review_section(
                developer_review
            ),
        },
        [repository_marker_location(request)],
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Ok(configuration):
            assert configuration.review == developer_review
        case Err(error):
            raise error


def test_project_review_section_survives_a_developer_project_config_without_one() -> (
    None
):
    request = ConfigurationRequest.fake()
    review = ReviewSettings.fake()
    files = InMemoryConfigFileStore(
        {
            project_config_location(request): review_section(review),
            developer_project_config_location(request): FileContent(""),
        },
        [repository_marker_location(request)],
    )

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), repository_names()
    )

    match result:
        case Ok(configuration):
            assert configuration.review == review
        case Err(error):
            raise error


def test_a_repository_that_cannot_be_named_is_an_error() -> None:
    request = ConfigurationRequest.fake()
    files = InMemoryConfigFileStore({}, [repository_marker_location(request)])

    result = load_configuration(
        request, files, InMemoryEnvironmentVariables({}), FakeRepositoryNames({})
    )

    assert isinstance(result, Err)


def test_outside_a_repository_no_repository_name_is_needed() -> None:
    result = load_configuration(
        ConfigurationRequest.fake(),
        InMemoryConfigFileStore({}),
        InMemoryEnvironmentVariables({}),
        FakeRepositoryNames({}),
    )

    assert isinstance(result, Ok)
