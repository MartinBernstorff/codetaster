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
