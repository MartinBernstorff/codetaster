from pathlib import Path
from typing import override

from pydantic import ConfigDict, RootModel

from codetaster_cli.domain.domain_model.command import WorkingDirectory


class CheckoutPath(RootModel[Path]):
    """The root directory of a git checkout (the main one or a worktree)."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    def working_directory(self) -> WorkingDirectory:
        return WorkingDirectory(self.root)

    @staticmethod
    def fake() -> CheckoutPath:
        return CheckoutPath(Path("/repo/main"))
