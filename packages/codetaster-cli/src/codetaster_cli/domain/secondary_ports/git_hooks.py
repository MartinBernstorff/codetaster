from typing import Protocol

from safe_result import Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError


class GitHooks(Protocol):
    """The git hooks that validate commits."""

    def install_hooks(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        """Install the hooks. Idempotent."""
        ...

    def uninstall_hooks(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        """Remove the hooks. Succeeds if none are installed."""
        ...
