from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.secondary_ports.toolchain import Toolchain


class FakeToolchain(Toolchain):
    """Keeps the checkouts it installed tools for in `installed`, so tests can inspect them."""

    def __init__(self, failure: ToolError | None = None) -> None:
        self.installed: set[CheckoutPath] = set()
        self.failure = failure

    @override
    def install_pinned_tools(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        if self.failure is not None:
            return Err(self.failure)
        self.installed.add(checkout)
        return Ok(None)
