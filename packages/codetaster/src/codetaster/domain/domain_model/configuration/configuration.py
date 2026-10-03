from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.configuration.secret_values import Secrets
from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.filesystem import Locations


class Configuration(BaseModel):
    """The effective configuration, and the files it was assembled from."""

    model_config = ConfigDict(frozen=True)

    settings: Settings
    secrets: Secrets
    loaded_files: Locations

    @staticmethod
    def fake() -> Configuration:
        return Configuration(
            settings=Settings.fake(),
            secrets=Secrets.fake(),
            loaded_files=Locations.fake(),
        )
