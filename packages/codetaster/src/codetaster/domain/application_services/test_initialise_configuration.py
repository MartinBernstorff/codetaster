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
from codetaster.infrastructure.config_file_store.in_memory import (
    InMemoryConfigFileStore,
)
from codetaster.infrastructure.config_file_store.toml_parsing import FileContent
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


def repository_store(
    repository: Location, files: dict[Location, FileContent] | None = None
) -> InMemoryConfigFileStore:
    marker = InitialisationRequest.fake().conventions.repository_marker
    return InMemoryConfigFileStore(files or {}, [repository.joinpath(marker)])


def test_project_file_is_written_at_the_nearest_repository_root() -> None:
    repository = Location.fake()
    request = request_from(repository.joinpath(PathName.fake()))
    expected = repository.joinpath(request.conventions.project_file)
    store = repository_store(repository)

    result = initialise_configuration(request, store, InMemoryEnvironmentVariables({}))

    assert result == Ok(expected)
    assert set(store.files) == {expected}


def test_written_file_loads_as_the_default_settings() -> None:
    repository = Location.fake()
    store = repository_store(repository)

    match initialise_configuration(
        request_from(repository), store, InMemoryEnvironmentVariables({})
    ):
        case Ok(location):
            document = store.read_document(location)
            assert isinstance(document, Ok)
            assert document.value is not None
            assert Settings.model_validate(document.value.root) == Settings()
        case Err(error):
            raise error


def test_outside_a_repository_is_an_error() -> None:
    working_directory = Location.fake()
    store = InMemoryConfigFileStore({})

    result = initialise_configuration(
        request_from(working_directory), store, InMemoryEnvironmentVariables({})
    )

    match result:
        case Err(NoProjectRootError() as error):
            assert error.start == working_directory
        case _:
            raise AssertionError(result)
    assert store.files == {}


def test_refuses_to_replace_an_existing_file() -> None:
    repository = Location.fake()
    request = request_from(repository)
    existing = repository.joinpath(request.conventions.project_file)
    original = {existing: FileContent.fake()}
    store = repository_store(repository, original)

    result = initialise_configuration(request, store, InMemoryEnvironmentVariables({}))

    match result:
        case Err(ConfigFileExistsError() as error):
            assert error.location == existing
        case _:
            raise AssertionError(result)
    assert store.files == original


def test_overwrite_replaces_an_existing_file() -> None:
    repository = Location.fake()
    request = request_from(repository, existing_file=ExistingFilePolicy.OVERWRITE)
    existing = repository.joinpath(request.conventions.project_file)
    original = FileContent.fake()
    store = repository_store(repository, {existing: original})

    result = initialise_configuration(request, store, InMemoryEnvironmentVariables({}))

    assert result == Ok(existing)
    assert store.files[existing] != original


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
    store = InMemoryConfigFileStore({})

    result = initialise_configuration(request, store, environment)

    assert result == Ok(expected)
    assert set(store.files) == {expected}


def test_developer_file_falls_back_to_dot_config_in_home() -> None:
    request = request_from(Location.fake(), scope=ConfigScope.DEVELOPER)
    conventions = request.conventions
    expected = (
        request.home.joinpath(conventions.fallback_config_home)
        .joinpath(conventions.app_directory)
        .joinpath(conventions.developer_file)
    )
    store = InMemoryConfigFileStore({})

    result = initialise_configuration(request, store, InMemoryEnvironmentVariables({}))

    assert result == Ok(expected)
    assert set(store.files) == {expected}


def test_write_failure_is_returned() -> None:
    request = request_from(
        Location.fake(),
        scope=ConfigScope.DEVELOPER,
        existing_file=ExistingFilePolicy.OVERWRITE,
    )
    conventions = request.conventions
    target = (
        request.home.joinpath(conventions.fallback_config_home)
        .joinpath(conventions.app_directory)
        .joinpath(conventions.developer_file)
    )

    result = initialise_configuration(
        request,
        InMemoryConfigFileStore({}, [target]),
        InMemoryEnvironmentVariables({}),
    )

    match result:
        case Err(ConfigFileError() as error):
            assert error.location == target
        case _:
            raise AssertionError(result)
