from pydantic import BaseModel, ConfigDict, RootModel

from codetaster.domain.domain_model.configuration.settings import Settings


class SettingName(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> SettingName:
        return SettingName("log_format")


class SettingDescription(RootModel[str]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> SettingDescription:
        return SettingDescription("How log lines are formatted.")


class SettingDefault(RootModel[object]):
    """A setting's default value, in its JSON-compatible form."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> SettingDefault:
        return SettingDefault("text")


class TemplateEntry(BaseModel):
    """One setting in a config file template. `default` is `None` if it has none."""

    model_config = ConfigDict(frozen=True)

    name: SettingName
    description: SettingDescription | None
    default: SettingDefault | None

    @staticmethod
    def fake() -> TemplateEntry:
        return TemplateEntry(
            name=SettingName.fake(),
            description=SettingDescription.fake(),
            default=SettingDefault.fake(),
        )


class SettingsTemplate(RootModel[tuple[TemplateEntry, ...]]):
    """Every setting with its default, for writing a starter config file."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> SettingsTemplate:
        return SettingsTemplate((TemplateEntry.fake(),))

    @staticmethod
    def from_settings_schema() -> SettingsTemplate:
        """One entry per `Settings` field, so new settings are included automatically."""
        defaults = Settings().model_dump(mode="json")
        return SettingsTemplate(
            tuple(
                TemplateEntry(
                    name=SettingName(name),
                    description=None
                    if field.description is None
                    else SettingDescription(field.description),
                    default=None
                    if defaults[name] is None
                    else SettingDefault(defaults[name]),
                )
                for name, field in Settings.model_fields.items()
            )
        )
