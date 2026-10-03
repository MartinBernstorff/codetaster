from codetaster_cli.domain.domain_model.worktrees import WorktreeCount
from codetaster_cli.infrastructure.external_tool.run_external_tool import ToolOutput
from codetaster_cli.infrastructure.git_worktrees.git_cli_worktrees import (
    count_porcelain_entries,
)


def test_counts_each_worktree_entry_in_porcelain_output() -> None:
    output = ToolOutput(
        "worktree /repo/main\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /repo/feature\nHEAD def\ndetached\n\n"
    )

    assert count_porcelain_entries(output) == WorktreeCount(2)
