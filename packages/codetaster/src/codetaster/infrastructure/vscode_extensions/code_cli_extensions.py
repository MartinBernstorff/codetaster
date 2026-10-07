from pathlib import Path
from typing import override

from pydantic import ConfigDict, RootModel
from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import InstallationHint, ToolError
from codetaster.domain.domain_model.vscode_extension import ExtensionPackagePath
from codetaster.domain.secondary_ports.vscode_extensions import VsCodeExtensions
from codetaster.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    ToolOutput,
    run_external_tool,
)


class VsCodeSandbox(RootModel[Path]):
    """A directory holding the extensions and user data of a throwaway VS Code."""

    model_config = ConfigDict(frozen=True)

    def arguments(self) -> ToolArguments:
        return ToolArguments(
            (
                "--extensions-dir",
                str(self.root / "extensions"),
                "--user-data-dir",
                str(self.root / "user-data"),
            )
        )

    @staticmethod
    def fake() -> VsCodeSandbox:
        return VsCodeSandbox(Path("/tmp/vscode-sandbox"))


class CodeCliExtensions(VsCodeExtensions):
    """Manages extensions with the `code` CLI.

    Acts on the user's VS Code, or on `sandbox` when given.
    """

    def __init__(self, sandbox: VsCodeSandbox | None = None) -> None:
        self.sandbox_arguments = (
            sandbox.arguments() if sandbox is not None else ToolArguments(())
        )
        self.hint = InstallationHint(
            "In VS Code, run 'Shell Command: Install 'code' command in PATH' "
            "from the Command Palette."
        )

    @override
    def install_extension_package(
        self, package: ExtensionPackagePath
    ) -> Result[None, ToolError]:
        return self._run_code(
            ToolArguments(("--install-extension", str(package), "--force")),
            OutputMode.SHOW,
        ).map(lambda _: None)

    def _run_code(
        self, arguments: ToolArguments, mode: OutputMode
    ) -> Result[ToolOutput, ToolError]:
        return run_external_tool(
            ToolArguments(("code", *self.sandbox_arguments.root, *arguments.root)),
            CheckoutPath(Path.cwd()),
            mode,
            self.hint,
        )
