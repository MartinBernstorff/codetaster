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


class LocalConfigFileReader(ConfigFileReader):
    @override
    def read_document(
        self, location: Location
    ) -> Result[ConfigDocument | None, ConfigFileError]:
        try:
            text = location.root.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Ok(None)
        except (OSError, UnicodeDecodeError) as error:
            return Err(ConfigFileError(location, ErrorReason(f"unreadable: {error}")))
        return parse_toml_document(FileContent(text), location)

    @override
    def exists(self, location: Location) -> bool:
        return location.root.exists()
