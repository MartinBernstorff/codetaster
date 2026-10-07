from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.vscode_extension import (
    AllowlistUpdate,
    ArgvFileError,
    ExtensionId,
    ExtensionIds,
)
from codetaster.domain.secondary_ports.proposed_api_allowlist import (
    ProposedApiAllowlist,
)


class InMemoryProposedApiAllowlist(ProposedApiAllowlist):
    """Keeps the allowed extensions in `allowed`, so tests can inspect them."""

    def __init__(self, failure: ArgvFileError | None = None) -> None:
        self.allowed: set[ExtensionId] = set()
        self.failure = failure

    @override
    def allow_proposed_api(
        self, extension: ExtensionId
    ) -> Result[AllowlistUpdate, ArgvFileError]:
        if self.failure is not None:
            return Err(self.failure)
        if ExtensionIds(frozenset(self.allowed)).includes(extension):
            return Ok(AllowlistUpdate.ALREADY_ALLOWED)
        self.allowed.add(extension)
        return Ok(AllowlistUpdate.ADDED)

    @override
    def list_allowed_extensions(self) -> Result[ExtensionIds, ArgvFileError]:
        if self.failure is not None:
            return Err(self.failure)
        return Ok(ExtensionIds(frozenset(self.allowed)))
