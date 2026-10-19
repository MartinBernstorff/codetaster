from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.command_line_tool import PythonPackagePath
from codetaster.domain.domain_model.tool_errors import ToolError


class CommandLineTools(Protocol):
    """Python packages installed for the user, so their commands are on PATH."""

    def install_command_line_tool(
        self, package: PythonPackagePath
    ) -> Result[None, ToolError]:
        """Install `package`, replacing any installed version. Idempotent.

        Rebuilds from source every time, so changes are installed even if the
        version did not change. The install does not depend on `package` staying
        where it is.
        """
        ...
