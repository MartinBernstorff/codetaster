from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.domain_model.vscode_extension import (
    ExtensionIds,
    ExtensionPackagePath,
)


class VsCodeExtensions(Protocol):
    """The extensions installed in VS Code, managed through the `code` CLI."""

    def install_extension_package(
        self, package: ExtensionPackagePath
    ) -> Result[None, ToolError]:
        """Install `package`, replacing any installed copy, even of the same version."""
        ...

    def list_installed_extensions(self) -> Result[ExtensionIds, ToolError]: ...
