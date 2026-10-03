from typing import override

from pydantic import ConfigDict, RootModel


class WorktreeCount(RootModel[int]):
    """How many checkouts (the main one plus linked worktrees) share a repository."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    def is_last_checkout(self) -> bool:
        return self.root <= 1

    def others(self) -> WorktreeCount:
        return WorktreeCount(self.root - 1)

    @staticmethod
    def fake() -> WorktreeCount:
        return WorktreeCount(1)
