"""Where config files live. Shared by the configuration use-cases."""

from pathlib import Path

from codetaster.domain.domain_model.configuration.conventions import (
    ConfigConventions,
)
from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.secondary_ports.config_file_store import ConfigFileStore
from codetaster.domain.secondary_ports.environment_variables import (
    EnvironmentVariables,
)


def resolve_config_root(
    home: Location, conventions: ConfigConventions, environment: EnvironmentVariables
) -> Location:
    """`$XDG_CONFIG_HOME/<app>`, or `~/.config/<app>` if that is unset or relative."""
    xdg_config_home = environment.value_of(conventions.xdg_config_home_variable)
    base = (
        Location(Path(xdg_config_home.root))
        if xdg_config_home is not None and Path(xdg_config_home.root).is_absolute()
        else home.joinpath(conventions.fallback_config_home)
    )
    return base.joinpath(conventions.app_directory)


def find_repository_root(
    start: Location, conventions: ConfigConventions, files: ConfigFileStore
) -> Location | None:
    """The nearest of `start` and its parents that contains the repository marker."""
    for directory in start.lineage().root:
        if files.exists(directory.joinpath(conventions.repository_marker)):
            return directory
    return None
