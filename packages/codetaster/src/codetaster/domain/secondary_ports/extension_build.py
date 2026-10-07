from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.domain_model.vscode_extension import (
    BuiltExtension,
    ExtensionPackageError,
)


class ExtensionBuild(Protocol):
    """Builds the forked VS Code extension into a `.vsix` package."""

    def build_extension_package(
        self, checkout: CheckoutPath
    ) -> Result[BuiltExtension, ToolError | ExtensionPackageError]:
        """Build and package the extension in `checkout`, reusing cached results."""
        ...
