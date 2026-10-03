"""Contract for ConfigFileReader, run against every implementation."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol

import pytest
from safe_result import Err, Ok

from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.filesystem import Location, PathName
from codetaster.domain.secondary_ports.config_file_reader import ConfigFileReader
from codetaster.infrastructure.config_file_reader.in_memory import (
    InMemoryConfigFileReader,
)
from codetaster.infrastructure.config_file_reader.local import LocalConfigFileReader
from codetaster.infrastructure.config_file_reader.toml_parsing import FileContent


class ReaderFactory(Protocol):
    def __call__(
        self,
        files: Mapping[Location, FileContent],
        directories: Iterable[Location] = (),
    ) -> ConfigFileReader: ...


def build_local_reader(
    files: Mapping[Location, FileContent], directories: Iterable[Location] = ()
) -> ConfigFileReader:
    for location, content in files.items():
        location.root.parent.mkdir(parents=True, exist_ok=True)
        _ = location.root.write_text(content.root, encoding="utf-8")
    for directory in directories:
        directory.root.mkdir(parents=True, exist_ok=True)
    return LocalConfigFileReader()


@pytest.fixture(params=["local", "in_memory"])
def build_reader(request: pytest.FixtureRequest) -> ReaderFactory:
    return build_local_reader if request.param == "local" else InMemoryConfigFileReader


@pytest.fixture
def root(tmp_path: Path) -> Location:
    return Location(tmp_path)


def test_missing_file_is_none(build_reader: ReaderFactory, root: Location) -> None:
    reader = build_reader({})

    assert reader.read_document(root.joinpath(PathName.fake())) == Ok(None)


def test_reads_toml_document(build_reader: ReaderFactory, root: Location) -> None:
    location = root.joinpath(PathName.fake())
    key = "log_format"
    value = "json"
    reader = build_reader({location: FileContent(f'{key} = "{value}"\n')})

    assert reader.read_document(location) == Ok(ConfigDocument({key: value}))


def test_malformed_toml_is_an_error_naming_the_file(
    build_reader: ReaderFactory, root: Location
) -> None:
    location = root.joinpath(PathName.fake())
    expected_reason = "invalid TOML"
    reader = build_reader({location: FileContent("log_format = \n")})

    match reader.read_document(location):
        case Err(error):
            assert error.location == location
            assert expected_reason in error.reason.root
        case Ok(value):
            pytest.fail(f"expected an error, got {value!r}")


def test_reading_a_directory_is_an_error(
    build_reader: ReaderFactory, root: Location
) -> None:
    directory = root.joinpath(PathName.fake())
    reader = build_reader({}, [directory])

    assert isinstance(reader.read_document(directory), Err)


def test_exists_for_files_and_directories(
    build_reader: ReaderFactory, root: Location
) -> None:
    file = root.joinpath(PathName("file"))
    directory = root.joinpath(PathName("directory"))
    reader = build_reader({file: FileContent.fake()}, [directory])

    assert reader.exists(file)
    assert reader.exists(directory)
    assert not reader.exists(root.joinpath(PathName("absent")))
