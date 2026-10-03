from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.configuration.review_settings import (
    ReviewSettings,
)
from codetaster.domain.domain_model.configuration.secret_values import Secrets
from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.filesystem import Locations


class Configuration(BaseModel):
    """The effective configuration, and the files it was assembled from."""

    model_config = ConfigDict(frozen=True)

    settings: Settings
    secrets: Secrets
    review: ReviewSettings | None
    loaded_files: Locations

    @staticmethod
    def fake() -> Configuration:
        return Configuration(
            settings=Settings.fake(),
            secrets=Secrets.fake(),
            review=ReviewSettings.fake(),
            loaded_files=Locations.fake(),
        )
