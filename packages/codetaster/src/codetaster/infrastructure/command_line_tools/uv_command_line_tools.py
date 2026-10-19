import os
from pathlib import Path
from typing import override

from pydantic import ConfigDict, RootModel
from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.command_line_tool import PythonPackagePath
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.tool_errors import InstallationHint, ToolError
from codetaster.domain.secondary_ports.command_line_tools import CommandLineTools
from codetaster.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    ToolEnvironment,
    run_external_tool,
)


class UvToolSandbox(RootModel[Path]):
    """A directory holding the tools and executables of a throwaway uv."""

    model_config = ConfigDict(frozen=True)

    def executables_directory(self) -> Location:
        return Location(self.root / "bin")

    def environment(self) -> ToolEnvironment:
        """This process's environment, with uv's tool directories in the sandbox."""
        return ToolEnvironment(
            {
                **os.environ,
                "UV_TOOL_DIR": str(self.root / "tools"),
                "UV_TOOL_BIN_DIR": str(self.executables_directory().root),
            }
        )

    @staticmethod
    def fake() -> UvToolSandbox:
        return UvToolSandbox(Path("/tmp/uv-tool-sandbox"))


class UvCommandLineTools(CommandLineTools):
    """Installs packages with `uv tool install`.

    Installs into the user's uv tools, or into `sandbox` when given.
    """

    def __init__(self, sandbox: UvToolSandbox | None = None) -> None:
        self.environment = sandbox.environment() if sandbox is not None else None

    @override
    def install_command_line_tool(
        self, package: PythonPackagePath
    ) -> Result[None, ToolError]:
        # `--reinstall` rebuilds the package; without it, uv reuses a cached build
        # of the same version and installs stale code.
        return run_external_tool(
            ToolArguments(
                ("uv", "tool", "install", "--force", "--reinstall", str(package))
            ),
            CheckoutPath(Path.cwd()),
            OutputMode.SHOW,
            InstallationHint("Install uv: https://docs.astral.sh/uv/"),
            self.environment,
        ).map(lambda _: None)
