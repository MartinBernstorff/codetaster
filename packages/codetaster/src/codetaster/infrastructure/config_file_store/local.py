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


class LocalConfigFileStore(ConfigFileStore):
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

    @override
    def write_template(
        self, location: Location, template: SettingsTemplate
    ) -> Result[None, ConfigFileError]:
        content = render_commented_template(template)
        try:
            location.root.parent.mkdir(parents=True, exist_ok=True)
            _ = location.root.write_text(content.root, encoding="utf-8")
        except OSError as error:
            return Err(ConfigFileError(location, ErrorReason(f"unwritable: {error}")))
        return Ok(None)
