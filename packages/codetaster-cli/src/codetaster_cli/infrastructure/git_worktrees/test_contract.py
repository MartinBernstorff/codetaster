"""Contract for GitWorktrees, run against every implementation."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from safe_result import Ok

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.worktrees import WorktreeCount
from codetaster_cli.domain.secondary_ports.git_worktrees import GitWorktrees
from codetaster_cli.infrastructure.fakes.call_log import CallLog
from codetaster_cli.infrastructure.git_worktrees.fake_git_worktrees import (
    FakeGitWorktrees,
)
from codetaster_cli.infrastructure.git_worktrees.git_cli_worktrees import (
    GitCliWorktrees,
)

type WorktreesFactory = Callable[[WorktreeCount], tuple[GitWorktrees, CheckoutPath]]


def git_repository_with(count: WorktreeCount, main: CheckoutPath) -> CheckoutPath:
    """Create a repository at `main`, with linked worktrees next to it."""
    main.root.mkdir()
    identity = ["-c", "user.name=test", "-c", "user.email=test@example.com"]
    commands = [
        ["git", "init", "--quiet"],
        ["git", *identity, "commit", "--quiet", "--allow-empty", "-m", "initial"],
        *(
            [
                "git",
                "worktree",
                "add",
                "--quiet",
                "--detach",
                str(main.root.parent / f"linked-{i}"),
            ]
            for i in range(count.root - 1)
        ),
    ]
    for command in commands:
        _ = subprocess.run(command, cwd=main.root, check=True)
    return main


@pytest.fixture(params=["git", "fake"])
def build_worktrees(request: pytest.FixtureRequest, tmp_path: Path) -> WorktreesFactory:
    def build(count: WorktreeCount) -> tuple[GitWorktrees, CheckoutPath]:
        if request.param == "git":
            return GitCliWorktrees(), git_repository_with(
                count, CheckoutPath(tmp_path / "main")
            )
        return FakeGitWorktrees(CallLog.fake(), count), CheckoutPath(tmp_path)

    return build


@pytest.mark.parametrize("count", [WorktreeCount(1), WorktreeCount(3)])
def test_counts_the_main_checkout_and_every_linked_worktree(
    build_worktrees: WorktreesFactory, count: WorktreeCount
) -> None:
    worktrees, checkout = build_worktrees(count)

    assert worktrees.count_worktrees(checkout) == Ok(count)
