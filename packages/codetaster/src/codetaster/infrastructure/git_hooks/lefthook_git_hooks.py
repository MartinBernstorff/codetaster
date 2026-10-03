from typing import override

from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import InstallationHint, ToolError
from codetaster.domain.secondary_ports.git_hooks import GitHooks
from codetaster.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    run_external_tool,
)


class LefthookGitHooks(GitHooks):
    """Hooks from `lefthook.yml`.

    lefthook is a dev dependency, so it is on PATH whenever this CLI runs through
    `uv run`.
    """

    @override
    def install_hooks(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        return run_external_tool(
            ToolArguments(("lefthook", "install")),
            checkout,
            OutputMode.SHOW,
            InstallationHint("Run this CLI through `uv run codetaster-manage`."),
        ).map(lambda _: None)
