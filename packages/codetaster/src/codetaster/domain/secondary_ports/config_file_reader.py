from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.configuration.errors import ConfigFileError
from codetaster.domain.domain_model.filesystem import Location


class ConfigFileReader(Protocol):
    def read_document(
        self, location: Location
    ) -> Result[ConfigDocument | None, ConfigFileError]:
        """The parsed file, `None` if nothing exists there, or why it is unreadable."""
        ...

    def exists(self, location: Location) -> bool:
        """Whether a file or directory exists at `location`."""
        ...
