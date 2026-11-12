from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.review.ratings import (
    RatingsFile,
    RatingsFileError,
    RatingsFileWriteError,
)
from codetaster.domain.domain_model.review.ratings_template import RatingsTemplate


class RatingsFileStore(Protocol):
    """Where the AI ratings file is kept."""

    def read_ratings(
        self, location: Location
    ) -> Result[RatingsFile | None, RatingsFileError]:
        """The parsed file, `None` if nothing exists there, or why it is invalid."""
        ...

    def write_template(
        self, location: Location, template: RatingsTemplate
    ) -> Result[None, RatingsFileWriteError]:
        """Write `template` as JSON for an agent to fill in.

        Creates missing parent directories and replaces any existing file.
        """
        ...
