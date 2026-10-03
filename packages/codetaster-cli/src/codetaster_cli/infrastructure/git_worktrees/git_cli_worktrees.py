from typing import override

from safe_result import Err, Ok, Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import InstallationHint, ToolError
from codetaster_cli.domain.domain_model.worktrees import WorktreeCount
from codetaster_cli.domain.secondary_ports.git_worktrees import GitWorktrees
from codetaster_cli.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    ToolOutput,
    run_external_tool,
)


class GitCliWorktrees(GitWorktrees):
    @override
    def count_worktrees(
        self, checkout: CheckoutPath
    ) -> Result[WorktreeCount, ToolError]:
        match run_external_tool(
            ToolArguments(("git", "worktree", "list", "--porcelain")),
            checkout,
            OutputMode.CAPTURE,
            InstallationHint("Install git: https://git-scm.com/downloads"),
        ):
            case Ok(output):
                return Ok(count_porcelain_entries(output))
            case Err() as failed:
                return failed


def count_porcelain_entries(output: ToolOutput) -> WorktreeCount:
    """Each checkout starts with a `worktree <path>` line in porcelain output."""
    return WorktreeCount(
        sum(1 for line in output.root.splitlines() if line.startswith("worktree "))
    )
