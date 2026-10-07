from enum import Enum, auto
from pathlib import Path
from typing import override

from pydantic import BaseModel, ConfigDict, RootModel

from codetaster.domain.domain_model.filesystem import Location


class ExtensionId(RootModel[str]):
    """A VS Code extension's `<publisher>.<name>`, compared case-insensitively."""

    model_config = ConfigDict(frozen=True)

    def normalised(self) -> ExtensionId:
        return ExtensionId(self.root.lower())

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> ExtensionId:
        return ExtensionId("codetaster.vscode-pull-request-github")


class ExtensionIds(RootModel[frozenset[ExtensionId]]):
    model_config = ConfigDict(frozen=True)

    def includes(self, extension: ExtensionId) -> bool:
        return extension.normalised() in {each.normalised() for each in self.root}

    @staticmethod
    def fake() -> ExtensionIds:
        return ExtensionIds(frozenset({ExtensionId.fake()}))


class ExtensionPackagePath(RootModel[Path]):
    """A packaged extension (`.vsix`) on disk."""

    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return str(self.root)

    @staticmethod
    def fake() -> ExtensionPackagePath:
        return ExtensionPackagePath(Path("/repo/main/vscode-extension/codetaster.vsix"))


class BuiltExtension(BaseModel):
    """A freshly packaged extension and the ID VS Code will know it by."""

    model_config = ConfigDict(frozen=True)

    package: ExtensionPackagePath
    extension_id: ExtensionId

    @staticmethod
    def fake() -> BuiltExtension:
        return BuiltExtension(
            package=ExtensionPackagePath.fake(), extension_id=ExtensionId.fake()
        )


class AllowlistUpdate(Enum):
    """Whether allowing an extension's proposed APIs changed anything."""

    ADDED = auto()
    ALREADY_ALLOWED = auto()


class ProblemDescription(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @override
    def __str__(self) -> str:
        return self.root

    @staticmethod
    def fake() -> ProblemDescription:
        return ProblemDescription("fake problem")


class ExtensionPackageError(Exception):
    """A build produced no usable extension package."""

    def __init__(self, problem: ProblemDescription) -> None:
        super().__init__(f"the extension build produced no usable package: {problem}")
        self.problem = problem

    @staticmethod
    def fake() -> ExtensionPackageError:
        return ExtensionPackageError(ProblemDescription.fake())


class ArgvFileError(Exception):
    """VS Code's `argv.json` cannot be read, parsed or written."""

    def __init__(self, location: Location, problem: ProblemDescription) -> None:
        super().__init__(f"{location.root}: {problem}")
        self.location = location
        self.problem = problem

    @staticmethod
    def fake() -> ArgvFileError:
        return ArgvFileError(Location.fake(), ProblemDescription.fake())
