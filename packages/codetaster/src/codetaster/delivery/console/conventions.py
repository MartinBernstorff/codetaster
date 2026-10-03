from codetaster.domain.domain_model.configuration.conventions import (
    ConfigConventions,
)
from codetaster.domain.domain_model.environment import VariableName
from codetaster.domain.domain_model.filesystem import PathName


def codetaster_conventions() -> ConfigConventions:
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
