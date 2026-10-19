from collections.abc import Mapping
from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.command_line_tool import (
    CommandName,
    CommandNames,
    PythonPackagePath,
)
from codetaster.domain.domain_model.tool_errors import (
    ExitCode,
    ToolError,
    ToolFailedError,
    ToolInvocation,
)
from codetaster.domain.secondary_ports.command_line_tools import CommandLineTools


class FakeCommandLineTools(CommandLineTools):
    """Installs the commands of the packages in `packages` into `installed`.

    Installing any other path fails, as uv does for a missing package.
    """

    def __init__(
        self,
        packages: Mapping[PythonPackagePath, CommandNames],
        failure: ToolError | None = None,
    ) -> None:
        self.packages = packages
        self.failure = failure
        self.installed: set[CommandName] = set()

    @override
    def install_command_line_tool(
        self, package: PythonPackagePath
    ) -> Result[None, ToolError]:
        if self.failure is not None:
            return Err(self.failure)
        if package not in self.packages:
            return Err(
                ToolFailedError(
                    ToolInvocation(f"uv tool install {package}"), ExitCode(2)
                )
            )
        self.installed.update(self.packages[package].root)
        return Ok(None)
