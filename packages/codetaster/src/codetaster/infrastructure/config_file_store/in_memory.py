from collections.abc import Iterable, Mapping
from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ErrorReason,
)
from codetaster.domain.domain_model.configuration.template import SettingsTemplate
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.secondary_ports.config_file_store import ConfigFileStore
from codetaster.infrastructure.config_file_store.commented_toml import (
    render_commented_template,
)
from codetaster.infrastructure.config_file_store.toml_parsing import (
    FileContent,
    parse_toml_document,
)


class InMemoryConfigFileStore(ConfigFileStore):
    """Keeps files in `files`, so tests can inspect what was written."""

    def __init__(
        self,
        files: Mapping[Location, FileContent],
        directories: Iterable[Location] = (),
    ) -> None:
        self.files = dict(files)
        self._directories = frozenset(directories)

    @override
    def read_document(
        self, location: Location
    ) -> Result[ConfigDocument | None, ConfigFileError]:
        if location in self._directories:
            return Err(
                ConfigFileError(location, ErrorReason("unreadable: a directory"))
            )
        content = self.files.get(location)
        if content is None:
            return Ok(None)
        return parse_toml_document(content, location)

    @override
    def exists(self, location: Location) -> bool:
        return location in self.files or location in self._directories

    @override
    def write_template(
        self, location: Location, template: SettingsTemplate
    ) -> Result[None, ConfigFileError]:
        if location in self._directories:
            return Err(
                ConfigFileError(location, ErrorReason("unwritable: a directory"))
            )
        self.files[location] = render_commented_template(template)
        return Ok(None)
