from collections.abc import Iterable, Mapping
from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ErrorReason,
)
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.secondary_ports.config_file_reader import ConfigFileReader
from codetaster.infrastructure.config_file_reader.toml_parsing import (
    FileContent,
    parse_toml_document,
)


class InMemoryConfigFileReader(ConfigFileReader):
    def __init__(
        self,
        files: Mapping[Location, FileContent],
        directories: Iterable[Location] = (),
    ) -> None:
        self._files = dict(files)
        self._directories = frozenset(directories)

    @override
    def read_document(
        self, location: Location
    ) -> Result[ConfigDocument | None, ConfigFileError]:
        if location in self._directories:
            return Err(
                ConfigFileError(location, ErrorReason("unreadable: a directory"))
            )
        content = self._files.get(location)
        if content is None:
            return Ok(None)
        return parse_toml_document(content, location)

    @override
    def exists(self, location: Location) -> bool:
        return location in self._files or location in self._directories
