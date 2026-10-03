from pathlib import Path
from typing import override

from pydantic import ConfigDict, RootModel


class CheckoutPath(RootModel[Path]):
    """The root directory of a git checkout (the main one or a worktree)."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> CheckoutPath:
        return CheckoutPath(Path("/repo/main"))
