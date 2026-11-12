"""Contract for RatingsFileStore, run against every implementation."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol

import pytest
from safe_result import Err, Ok

from codetaster.domain.domain_model.filesystem import Location, PathName
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileContent,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.secondary_ports.ratings_file_store import RatingsFileStore
from codetaster.infrastructure.ratings_file_store.in_memory import (
    InMemoryRatingsFileStore,
)
from codetaster.infrastructure.ratings_file_store.local import LocalRatingsFileStore


class StoreFactory(Protocol):
    def __call__(
        self,
        files: Mapping[Location, RatingsFileContent],
        directories: Iterable[Location] = (),
    ) -> RatingsFileStore: ...


def build_local_store(
    files: Mapping[Location, RatingsFileContent], directories: Iterable[Location] = ()
) -> RatingsFileStore:
    for location, content in files.items():
        location.root.parent.mkdir(parents=True, exist_ok=True)
        _ = location.root.write_text(content.root, encoding="utf-8")
    for directory in directories:
        directory.root.mkdir(parents=True, exist_ok=True)
    return LocalRatingsFileStore()


def build_in_memory_store(
    files: Mapping[Location, RatingsFileContent], directories: Iterable[Location] = ()
) -> RatingsFileStore:
    return InMemoryRatingsFileStore(files, directories)


@pytest.fixture(params=["local", "in_memory"])
def build_store(request: pytest.FixtureRequest) -> StoreFactory:
    return build_local_store if request.param == "local" else build_in_memory_store


@pytest.fixture
def location(tmp_path: Path) -> Location:
    return Location(tmp_path).joinpath(PathName("ratings.json"))


def test_missing_file_is_none(build_store: StoreFactory, location: Location) -> None:
    store = build_store({})

    assert store.read_ratings(location) == Ok(None)


def test_reads_ratings(build_store: StoreFactory, location: Location) -> None:
    ratings = RatingsFile.fake()
    store = build_store(
        {location: RatingsFileContent(ratings.model_dump_json(indent=2))}
    )

    assert store.read_ratings(location) == Ok(ratings)


def test_invalid_file_is_an_error_naming_the_file(
    build_store: StoreFactory, location: Location
) -> None:
    store = build_store({location: RatingsFileContent('{"ratings": [{}]}')})

    match store.read_ratings(location):
        case Err(error):
            assert error.location == location
        case Ok(value):
            pytest.fail(f"expected an error, got {value!r}")


def test_reading_a_directory_is_an_error(
    build_store: StoreFactory, location: Location
) -> None:
    store = build_store({}, [location])

    assert isinstance(store.read_ratings(location), Err)


def test_nothing_exists_at_a_missing_location(
    build_store: StoreFactory, location: Location
) -> None:
    store = build_store({})

    assert not store.exists(location)


def test_a_directory_exists(build_store: StoreFactory, location: Location) -> None:
    store = build_store({}, [location])

    assert store.exists(location)


def test_a_written_template_exists(
    build_store: StoreFactory, location: Location
) -> None:
    store = build_store({})

    _ = store.write_template(location, RatingsTemplate.fake())

    assert store.exists(location)


def test_writing_a_template_replaces_an_existing_file(
    build_store: StoreFactory, location: Location
) -> None:
    store = build_store(
        {location: RatingsFileContent(RatingsFile.fake().model_dump_json())}
    )

    assert store.write_template(location, RatingsTemplate.fake()) == Ok(None)

    # An unfilled template is not a valid ratings file.
    assert isinstance(store.read_ratings(location), Err)


def test_writing_a_template_over_a_directory_is_an_error_naming_it(
    build_store: StoreFactory, location: Location
) -> None:
    store = build_store({}, [location])

    match store.write_template(location, RatingsTemplate.fake()):
        case Err(error):
            assert error.location == location
        case Ok():
            pytest.fail("expected an error")


def test_writing_a_template_creates_missing_directories(tmp_path: Path) -> None:
    location = Location(tmp_path / "missing" / "ratings.json")

    _ = LocalRatingsFileStore().write_template(location, RatingsTemplate.fake())

    assert (
        RatingsTemplate.model_validate_json(location.root.read_text(encoding="utf-8"))
        == RatingsTemplate.fake()
    )
