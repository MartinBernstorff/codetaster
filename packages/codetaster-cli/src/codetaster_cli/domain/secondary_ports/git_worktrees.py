from typing import Protocol

from safe_result import Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError
from codetaster_cli.domain.domain_model.worktrees import WorktreeCount


class GitWorktrees(Protocol):
    """The checkouts that share a git repository."""

    def count_worktrees(
        self, checkout: CheckoutPath
    ) -> Result[WorktreeCount, ToolError]:
        """Count the checkouts of the repository `checkout` belongs to."""
        ...
