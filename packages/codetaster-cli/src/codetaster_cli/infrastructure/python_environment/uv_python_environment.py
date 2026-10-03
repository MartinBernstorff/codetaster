import shutil
from typing import override

from safe_result import Ok, Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import InstallationHint, ToolError
from codetaster_cli.domain.secondary_ports.python_environment import (
    PythonEnvironment,
)
from codetaster_cli.infrastructure.external_tool.run_external_tool import (
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

    @override
    def remove_virtualenv(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        shutil.rmtree(checkout.root / ".venv", ignore_errors=True)
        return Ok(None)
