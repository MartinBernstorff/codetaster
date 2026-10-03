from typing import Protocol

from safe_result import Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError


class TaskCache(Protocol):
    """Cached results from the task runner."""

    def clear_cache(self, checkout: CheckoutPath) -> Result[None, ToolError]:
        """Delete cached results. Succeeds if there are none."""
        ...
