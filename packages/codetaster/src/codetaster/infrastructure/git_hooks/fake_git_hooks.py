from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.secondary_ports.git_hooks import GitHooks


class FakeGitHooks(GitHooks):
    """Keeps the checkouts it installed hooks in in `hooked`, so tests can inspect them."""

    def __init__(self, failure: ToolError | None = None) -> None:
        self.hooked: set[CheckoutPath] = set()
        self.failure = failure

    @override
    def install_hooks(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        if self.failure is not None:
            return Err(self.failure)
        self.hooked.add(checkout)
        return Ok(None)
