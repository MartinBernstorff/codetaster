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
