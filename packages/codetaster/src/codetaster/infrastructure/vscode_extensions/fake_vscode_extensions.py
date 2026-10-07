from collections.abc import Mapping
from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.tool_errors import (
    ExitCode,
    ToolError,
    ToolFailedError,
    ToolInvocation,
)
from codetaster.domain.domain_model.vscode_extension import (
    ExtensionId,
    ExtensionPackagePath,
)
from codetaster.domain.secondary_ports.vscode_extensions import VsCodeExtensions


class FakeVsCodeExtensions(VsCodeExtensions):
    """Installs the packages in `packages`, keyed by path, into `installed`.

    Installing any other path fails, as `code` does for a missing file.
    """

    def __init__(
        self,
        packages: Mapping[ExtensionPackagePath, ExtensionId],
        failure: ToolError | None = None,
    ) -> None:
        self.packages = packages
        self.failure = failure
        self.installed: set[ExtensionId] = set()

    @override
    def install_extension_package(
        self, package: ExtensionPackagePath
    ) -> Result[None, ToolError]:
        if self.failure is not None:
            return Err(self.failure)
        if package not in self.packages:
            return Err(
                ToolFailedError(
                    ToolInvocation(f"code --install-extension {package}"), ExitCode(1)
                )
            )
        self.installed.add(self.packages[package])
        return Ok(None)
