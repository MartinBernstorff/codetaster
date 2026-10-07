from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileError,
)


class RatingsFileStore(Protocol):
    """Where the AI ratings file is kept."""

    def read_ratings(
        self, location: Location
    ) -> Result[RatingsFile | None, RatingsFileError]:
        """The parsed file, `None` if nothing exists there, or why it is invalid."""
        ...
