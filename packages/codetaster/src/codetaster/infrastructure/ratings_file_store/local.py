from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.configuration.errors import ErrorReason
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileContent,
    RatingsFileError,
    RatingsFileWriteError,
    parse_ratings_file,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate
from codetaster.domain.secondary_ports.ratings_file_store import RatingsFileStore


class LocalRatingsFileStore(RatingsFileStore):
    @override
    def read_ratings(
        self, location: Location
    ) -> Result[RatingsFile | None, RatingsFileError]:
        try:
            text = location.root.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Ok(None)
        except (OSError, UnicodeDecodeError) as error:
            return Err(RatingsFileError(location, ErrorReason(f"unreadable: {error}")))
        return parse_ratings_file(RatingsFileContent(text), location)

    @override
    def exists(self, location: Location) -> bool:
        return location.root.exists()

    @override
    def write_template(
        self, location: Location, template: RatingsTemplate
    ) -> Result[None, RatingsFileWriteError]:
        try:
            location.root.parent.mkdir(parents=True, exist_ok=True)
            _ = location.root.write_text(
                template.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
        except OSError as error:
            return Err(
                RatingsFileWriteError(location, ErrorReason(f"unwritable: {error}"))
            )
        return Ok(None)
