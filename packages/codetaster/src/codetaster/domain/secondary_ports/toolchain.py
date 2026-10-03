from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError


class Toolchain(Protocol):
    """The pinned developer tools (moon, Python, uv)."""

    def install_pinned_tools(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        """Install the tool versions pinned for `checkout`. Idempotent."""
        ...
