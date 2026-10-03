from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.configuration.errors import ConfigFileError
from codetaster.domain.domain_model.configuration.template import SettingsTemplate
from codetaster.domain.domain_model.filesystem import Location


class ConfigFileWriter(Protocol):
    def write_template(
        self, location: Location, template: SettingsTemplate
    ) -> Result[None, ConfigFileError]:
        """Write a config file listing every setting commented out at its default.

        Creates missing parent directories and replaces any existing file.
        """
        ...
