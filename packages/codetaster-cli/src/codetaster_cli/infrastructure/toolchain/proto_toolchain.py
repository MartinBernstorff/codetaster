from typing import override

from safe_result import Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import InstallationHint, ToolError
from codetaster_cli.domain.secondary_ports.toolchain import Toolchain
from codetaster_cli.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    run_external_tool,
)


class ProtoToolchain(Toolchain):
    """Installs the versions pinned in `.prototools`."""

    @override
    def install_pinned_tools(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        return run_external_tool(
            ToolArguments(("proto", "install")),
            checkout,
            OutputMode.SHOW,
            InstallationHint(
                "Install proto with the instructions at "
                "https://moonrepo.dev/docs/proto/install, open a new shell, then "
                "re-run `uv run codetaster-cli setup`."
            ),
        ).map(lambda _: None)
