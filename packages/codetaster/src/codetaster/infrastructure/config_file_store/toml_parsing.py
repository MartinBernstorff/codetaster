import tomllib

from pydantic import RootModel
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.configuration.errors import (
    ConfigFileError,
    ErrorReason,
)
from codetaster.domain.domain_model.filesystem import Location


class FileContent(RootModel[str]):
    @staticmethod
    def fake() -> FileContent:
        return FileContent("")


def parse_toml_document(
    content: FileContent, location: Location
) -> Result[ConfigDocument, ConfigFileError]:
    try:
        parsed = tomllib.loads(content.root)
    except tomllib.TOMLDecodeError as error:
        return Err(ConfigFileError(location, ErrorReason(f"invalid TOML: {error}")))
    return Ok(ConfigDocument(parsed))
