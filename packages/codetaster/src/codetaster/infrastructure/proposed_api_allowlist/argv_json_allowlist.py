from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.vscode_extension import (
    AllowlistUpdate,
    ArgvFileError,
    ExtensionId,
    ExtensionIds,
    ProblemDescription,
)
from codetaster.domain.secondary_ports.proposed_api_allowlist import (
    ProposedApiAllowlist,
)
from codetaster.infrastructure.proposed_api_allowlist.jsonc_document import (
    JsoncText,
    JsonKey,
    JsonString,
    append_to_string_list,
    read_string_list,
)


class ArgvJsonAllowlist(ProposedApiAllowlist):
    """The `enable-proposed-api` list in VS Code's `argv.json` at `location`.

    VS Code keeps the file at `~/.vscode/argv.json`. A missing file is created.
    """

    def __init__(self, location: Location) -> None:
        self.location = location
        self.key = JsonKey("enable-proposed-api")

    @override
    def allow_proposed_api(
        self, extension: ExtensionId
    ) -> Result[AllowlistUpdate, ArgvFileError]:
        match self._read_text():
            case Err() as failed:
                return failed
            case Ok(text):
                pass
        match self._allowed_in(text):
            case Err() as failed:
                return failed
            case Ok(allowed) if extension.normalised() in allowed.normalised().root:
                return Ok(AllowlistUpdate.ALREADY_ALLOWED)
            case Ok():
                pass
        match append_to_string_list(text, self.key, JsonString(extension.root)):
            case Err(invalid):
                return Err(ArgvFileError(self.location, invalid.problem))
            case Ok(updated):
                pass
        try:
            self.location.root.parent.mkdir(parents=True, exist_ok=True)
            _ = self.location.root.write_text(updated.root, encoding="utf-8")
        except OSError as error:
            return Err(
                ArgvFileError(self.location, ProblemDescription(f"unwritable: {error}"))
            )
        return Ok(AllowlistUpdate.ADDED)

    def _allowed_in(self, text: JsoncText) -> Result[ExtensionIds, ArgvFileError]:
        match read_string_list(text, self.key):
            case Err(invalid):
                return Err(ArgvFileError(self.location, invalid.problem))
            case Ok(values):
                return Ok(
                    ExtensionIds(
                        frozenset(ExtensionId(value.root) for value in values.root)
                    )
                )

    def _read_text(self) -> Result[JsoncText, ArgvFileError]:
        try:
            return Ok(JsoncText(self.location.root.read_text(encoding="utf-8-sig")))
        except FileNotFoundError:
            return Ok(JsoncText(""))
        except (OSError, UnicodeDecodeError) as error:
            return Err(
                ArgvFileError(self.location, ProblemDescription(f"unreadable: {error}"))
            )
