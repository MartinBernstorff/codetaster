from pathlib import Path

from safe_result import Err, Ok

from codetaster.domain.application_services.initialise_configuration import (
    ConfigScope,
    ExistingFilePolicy,
    InitialisationRequest,
    initialise_configuration,
)
from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ConfigFileExistsError,
    NoProjectRootError,
)
from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.environment import VariableValue
from codetaster.domain.domain_model.filesystem import Location, PathName

# Domain tests use the fakes from infrastructure, which tach otherwise forbids.
from codetaster.infrastructure.config_file_reader.in_memory import (
    InMemoryConfigFileReader,
)
from codetaster.infrastructure.config_file_reader.toml_parsing import (
    FileContent,
    parse_toml_document,
)
from codetaster.infrastructure.config_file_writer.in_memory import (
    InMemoryConfigFileWriter,
)
from codetaster.infrastructure.environment_variables.in_memory import (
    InMemoryEnvironmentVariables,
)


def request_from(
    working_directory: Location,
    scope: ConfigScope = ConfigScope.PROJECT,
    existing_file: ExistingFilePolicy = ExistingFilePolicy.REFUSE,
) -> InitialisationRequest:
    return InitialisationRequest.fake().model_copy(
        update={
            "working_directory": working_directory,
            "scope": scope,
            "existing_file": existing_file,
        }
    )


def repository_reader(repository: Location) -> InMemoryConfigFileReader:
    marker = InitialisationRequest.fake().conventions.repository_marker
    return InMemoryConfigFileReader({}, [repository.joinpath(marker)])


def test_project_file_is_written_at_the_nearest_repository_root() -> None:
    repository = Location.fake()
    request = request_from(repository.joinpath(PathName.fake()))
    expected = repository.joinpath(request.conventions.project_file)
    writer = InMemoryConfigFileWriter()

    result = initialise_configuration(
        request,
        repository_reader(repository),
        writer,
        InMemoryEnvironmentVariables({}),
    )

    assert result == Ok(expected)
    assert set(writer.written) == {expected}


def test_written_file_loads_as_the_default_settings() -> None:
    repository = Location.fake()
    writer = InMemoryConfigFileWriter()

    match initialise_configuration(
        request_from(repository),
        repository_reader(repository),
        writer,
        InMemoryEnvironmentVariables({}),
    ):
        case Ok(location):
            parsed = parse_toml_document(writer.written[location], location)
            assert isinstance(parsed, Ok)
            assert Settings.model_validate(parsed.value.root) == Settings()
        case Err(error):
            raise error


def test_outside_a_repository_is_an_error() -> None:
    working_directory = Location.fake()
    writer = InMemoryConfigFileWriter()

    result = initialise_configuration(
        request_from(working_directory),
        InMemoryConfigFileReader({}),
        writer,
        InMemoryEnvironmentVariables({}),
    )

    match result:
        case Err(NoProjectRootError() as error):
            assert error.start == working_directory
        case _:
            raise AssertionError(result)
    assert writer.written == {}


def test_refuses_to_replace_an_existing_file() -> None:
    repository = Location.fake()
    request = request_from(repository)
    existing = repository.joinpath(request.conventions.project_file)
    marker = repository.joinpath(request.conventions.repository_marker)
    files = InMemoryConfigFileReader({existing: FileContent.fake()}, [marker])
    writer = InMemoryConfigFileWriter()

    result = initialise_configuration(
        request, files, writer, InMemoryEnvironmentVariables({})
    )

    match result:
        case Err(ConfigFileExistsError() as error):
            assert error.location == existing
        case _:
            raise AssertionError(result)
    assert writer.written == {}


def test_overwrite_replaces_an_existing_file() -> None:
    repository = Location.fake()
    request = request_from(repository, existing_file=ExistingFilePolicy.OVERWRITE)
    existing = repository.joinpath(request.conventions.project_file)
    marker = repository.joinpath(request.conventions.repository_marker)
    files = InMemoryConfigFileReader({existing: FileContent.fake()}, [marker])
    writer = InMemoryConfigFileWriter()

    result = initialise_configuration(
        request, files, writer, InMemoryEnvironmentVariables({})
    )

    assert result == Ok(existing)
    assert set(writer.written) == {existing}


def test_developer_file_is_written_under_xdg_config_home() -> None:
    request = request_from(Location.fake(), scope=ConfigScope.DEVELOPER)
    conventions = request.conventions
    xdg_config_home = Location(Path("/xdg"))
    expected = xdg_config_home.joinpath(conventions.app_directory).joinpath(
        conventions.developer_file
    )
    environment = InMemoryEnvironmentVariables(
        {conventions.xdg_config_home_variable: VariableValue(str(xdg_config_home.root))}
    )

    result = initialise_configuration(
        request, InMemoryConfigFileReader({}), InMemoryConfigFileWriter(), environment
    )

    assert result == Ok(expected)


def test_developer_file_falls_back_to_dot_config_in_home() -> None:
    request = request_from(Location.fake(), scope=ConfigScope.DEVELOPER)
    conventions = request.conventions
    expected = (
        request.home.joinpath(conventions.fallback_config_home)
        .joinpath(conventions.app_directory)
        .joinpath(conventions.developer_file)
    )

    result = initialise_configuration(
        request,
        InMemoryConfigFileReader({}),
        InMemoryConfigFileWriter(),
        InMemoryEnvironmentVariables({}),
    )

    assert result == Ok(expected)


def test_write_failure_is_returned() -> None:
    request = request_from(Location.fake(), scope=ConfigScope.DEVELOPER)
    conventions = request.conventions
    target = (
        request.home.joinpath(conventions.fallback_config_home)
        .joinpath(conventions.app_directory)
        .joinpath(conventions.developer_file)
    )

    result = initialise_configuration(
        request,
        InMemoryConfigFileReader({}),
        InMemoryConfigFileWriter([target]),
        InMemoryEnvironmentVariables({}),
    )

    match result:
        case Err(ConfigFileError() as error):
            assert error.location == target
        case _:
            raise AssertionError(result)
