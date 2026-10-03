from typing import Protocol

from safe_result import Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError


class PythonEnvironment(Protocol):
    """The checkout's virtualenv and its locked dependencies."""

    def sync_dependencies(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        """Make the virtualenv match the lockfile exactly. Idempotent."""
        ...
