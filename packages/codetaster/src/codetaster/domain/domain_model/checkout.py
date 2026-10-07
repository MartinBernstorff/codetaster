from pathlib import Path
from typing import Annotated, override

from pydantic import ConfigDict, Field, RootModel


class CheckoutPath(RootModel[Path]):
    """The root directory of a git checkout (the main one or a worktree)."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> CheckoutPath:
        return CheckoutPath(Path("/repo/main"))


class RepositoryName(RootModel[Annotated[str, Field(min_length=1)]]):
    """What a repository is called, shared by its main checkout and every worktree."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> RepositoryName:
        return RepositoryName("repo")
