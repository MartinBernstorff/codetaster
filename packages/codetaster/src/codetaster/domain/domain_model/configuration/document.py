from pydantic import RootModel


class ConfigDocument(RootModel[dict[str, object]]):
    """The parsed but not yet validated contents of a config file."""

    @staticmethod
    def fake() -> ConfigDocument:
        return ConfigDocument({})
