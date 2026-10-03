from collections.abc import Iterable
from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ErrorReason,
)
from codetaster.domain.domain_model.configuration.template import SettingsTemplate
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.secondary_ports.config_file_writer import ConfigFileWriter
from codetaster.infrastructure.config_file_reader.toml_parsing import FileContent
from codetaster.infrastructure.config_file_writer.commented_toml import (
    render_commented_template,
)


class InMemoryConfigFileWriter(ConfigFileWriter):
    """Keeps written files in `written`, so tests can inspect them."""

    def __init__(self, directories: Iterable[Location] = ()) -> None:
        self.written: dict[Location, FileContent] = {}
        self._directories = frozenset(directories)

    @override
    def write_template(
        self, location: Location, template: SettingsTemplate
    ) -> Result[None, ConfigFileError]:
        if location in self._directories:
            return Err(
                ConfigFileError(location, ErrorReason("unwritable: a directory"))
            )
        self.written[location] = render_commented_template(template)
        return Ok(None)
