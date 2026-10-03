from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class LogFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


class Settings(BaseModel):
    """Non-secret configuration, read from developer and project config files.

    Every field has a default, so a file only lists what it overrides.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_format: LogFormat = LogFormat.TEXT

    @staticmethod
    def fake() -> Settings:
        return Settings(log_format=LogFormat.TEXT)

    def overridden_by(self, override: Settings) -> Settings:
        """Fields explicitly set in `override` win; the rest keep this value."""
        return Settings.model_validate(
            self.model_dump() | override.model_dump(exclude_unset=True)
        )
