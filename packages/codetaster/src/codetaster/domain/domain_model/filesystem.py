from pathlib import Path

from pydantic import ConfigDict, RootModel


class PathName(RootModel[str]):
    """A single file or directory name, such as `codetaster.toml` or `.git`."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> PathName:
        return PathName("codetaster.toml")


class Location(RootModel[Path]):
    """A path on the local filesystem."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> Location:
        return Location(Path("/fake"))

    def joinpath(self, name: PathName) -> Location:
        return Location(self.root / name.root)

    def lineage(self) -> Locations:
        """This location followed by each of its parents, nearest first."""
        return Locations((self, *(Location(parent) for parent in self.root.parents)))


class Locations(RootModel[tuple[Location, ...]]):
    @staticmethod
    def fake() -> Locations:
        return Locations((Location.fake(),))
