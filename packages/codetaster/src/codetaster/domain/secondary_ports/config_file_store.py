from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.configuration.errors import ConfigFileError
from codetaster.domain.domain_model.configuration.template import SettingsTemplate
from codetaster.domain.domain_model.filesystem import Location


class ConfigFileStore(Protocol):
    def read_document(
        self, location: Location
    ) -> Result[ConfigDocument | None, ConfigFileError]:
        """The parsed file, `None` if nothing exists there, or why it is unreadable."""
        ...

    def exists(self, location: Location) -> bool:
        """Whether a file or directory exists at `location`."""
        ...

    def write_template(
        self, location: Location, template: SettingsTemplate
    ) -> Result[None, ConfigFileError]:
        """Write a config file listing every setting commented out at its default.

        Creates missing parent directories and replaces any existing file.
        """
        ...
