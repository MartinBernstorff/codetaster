from typing import override

from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import InstallationHint, ToolError
from codetaster.domain.secondary_ports.python_environment import (
    PythonEnvironment,
)
from codetaster.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    run_external_tool,
)


class UvPythonEnvironment(PythonEnvironment):
    """The `.venv` that uv manages from `uv.lock`."""

    @override
    def sync_dependencies(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        return run_external_tool(
            ToolArguments(("uv", "sync", "--locked")),
            checkout,
            OutputMode.SHOW,
            InstallationHint("Install uv: https://docs.astral.sh/uv/"),
        ).map(lambda _: None)
