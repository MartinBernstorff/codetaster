from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ErrorReason,
)
from codetaster.domain.domain_model.configuration.template import SettingsTemplate
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.secondary_ports.config_file_writer import ConfigFileWriter
from codetaster.infrastructure.config_file_writer.commented_toml import (
    render_commented_template,
)


class LocalConfigFileWriter(ConfigFileWriter):
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
