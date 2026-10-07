from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.vscode_extension import (
    AllowlistUpdate,
    ArgvFileError,
    ExtensionId,
    ExtensionIds,
)


class ProposedApiAllowlist(Protocol):
    """The extensions VS Code lets use proposed APIs (`enable-proposed-api`).

    VS Code reads the list at startup, so changes apply after a restart.
    """

    def allow_proposed_api(
        self, extension: ExtensionId
    ) -> Result[AllowlistUpdate, ArgvFileError]:
        """Add `extension` to the list, keeping everything else. Idempotent."""
        ...

    def list_allowed_extensions(self) -> Result[ExtensionIds, ArgvFileError]: ...
