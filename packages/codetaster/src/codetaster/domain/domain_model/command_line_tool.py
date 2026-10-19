from pathlib import Path
from typing import override

from pydantic import ConfigDict, RootModel


class PythonPackagePath(RootModel[Path]):
    """The directory of a Python package's source, holding its `pyproject.toml`."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> PythonPackagePath:
        return PythonPackagePath(Path("/repo/main/packages/codetaster"))


class CommandName(RootModel[str]):
    """An executable a package puts on PATH, such as `codetaster`."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> CommandName:
        return CommandName("codetaster")


class CommandNames(RootModel[frozenset[CommandName]]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> CommandNames:
        return CommandNames(frozenset({CommandName.fake()}))
