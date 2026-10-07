from collections.abc import Iterable, Mapping
from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.configuration.errors import ErrorReason
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileContent,
    RatingsFileError,
    parse_ratings_file,
)
from codetaster.domain.secondary_ports.ratings_file_store import RatingsFileStore


class InMemoryRatingsFileStore(RatingsFileStore):
    """Keeps files in `files`, so tests can add, change or remove them."""

    def __init__(
        self,
        files: Mapping[Location, RatingsFileContent],
        directories: Iterable[Location] = (),
    ) -> None:
        self.files = dict(files)
        self._directories = frozenset(directories)

    def write_ratings(self, location: Location, ratings: RatingsFile) -> None:
        self.files[location] = RatingsFileContent(ratings.model_dump_json(indent=2))

    @override
    def read_ratings(
        self, location: Location
    ) -> Result[RatingsFile | None, RatingsFileError]:
        if location in self._directories:
            return Err(
                RatingsFileError(location, ErrorReason("unreadable: a directory"))
            )
        content = self.files.get(location)
        if content is None:
            return Ok(None)
        return parse_ratings_file(content, location)
