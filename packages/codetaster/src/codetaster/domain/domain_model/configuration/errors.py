from pydantic import RootModel

from codetaster.domain.domain_model.filesystem import Location


class ErrorReason(RootModel[str]):
    @staticmethod
    def fake() -> ErrorReason:
        return ErrorReason("fake reason")


class ConfigFileError(Exception):
    """A config file exists but cannot be read, parsed or validated."""

    def __init__(self, location: Location, reason: ErrorReason) -> None:
        super().__init__(f"{location.root}: {reason.root}")
        self.location = location
        self.reason = reason

    @staticmethod
    def fake() -> ConfigFileError:
        return ConfigFileError(Location.fake(), ErrorReason.fake())


class NoProjectRootError(Exception):
    """No repository root was found at or above `start`."""

    def __init__(self, start: Location) -> None:
        super().__init__(
            f"no project root (git repository) found at or above {start.root}"
        )
        self.start = start

    @staticmethod
    def fake() -> NoProjectRootError:
        return NoProjectRootError(Location.fake())


class ConfigFileExistsError(Exception):
    """A config file is already at `location`, and overwriting was not requested."""

    def __init__(self, location: Location) -> None:
        super().__init__(f"{location.root} already exists")
        self.location = location

    @staticmethod
    def fake() -> ConfigFileExistsError:
        return ConfigFileExistsError(Location.fake())
