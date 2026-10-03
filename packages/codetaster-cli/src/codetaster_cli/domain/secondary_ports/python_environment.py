from typing import Protocol

from safe_result import Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError


class PythonEnvironment(Protocol):
    """The checkout's virtualenv and its locked dependencies."""

    def sync_dependencies(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        """Make the virtualenv match the lockfile exactly. Idempotent."""
        ...

    def remove_virtualenv(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        """Delete the virtualenv. Succeeds if there is none."""
        ...
