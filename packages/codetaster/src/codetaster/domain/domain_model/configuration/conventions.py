from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.environment import VariableName
from codetaster.domain.domain_model.filesystem import PathName


class ConfigConventions(BaseModel):
    """Where configuration is looked for. Supplied by the composition root."""

    model_config = ConfigDict(frozen=True)

    app_directory: PathName
    xdg_config_home_variable: VariableName
    fallback_config_home: PathName
    developer_file: PathName
    secrets_file: PathName
    project_file: PathName
    repository_marker: PathName
    api_token_variable: VariableName

    @staticmethod
    def fake() -> ConfigConventions:
        return ConfigConventions(
            app_directory=PathName("codetaster"),
            xdg_config_home_variable=VariableName("XDG_CONFIG_HOME"),
            fallback_config_home=PathName(".config"),
            developer_file=PathName("config.toml"),
            secrets_file=PathName("secrets.toml"),
            project_file=PathName("codetaster.toml"),
            repository_marker=PathName(".git"),
            api_token_variable=VariableName("CODETASTER_API_TOKEN"),
        )
