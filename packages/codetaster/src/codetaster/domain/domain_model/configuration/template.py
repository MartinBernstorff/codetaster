from typing import get_args

from pydantic import BaseModel, ConfigDict, RootModel, TypeAdapter
from pydantic.fields import FieldInfo


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
    """One setting in a config file template. `default` is `None` if it has none.

    `section` is the table the setting belongs to, or `None` for the top level.
    """

    model_config = ConfigDict(frozen=True)

    name: SettingName
    section: SettingName | None
    description: SettingDescription | None
    default: SettingDefault | None

    @staticmethod
    def fake() -> TemplateEntry:
        return TemplateEntry(
            name=SettingName.fake(),
            section=None,
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
    def from_settings_schema(settings_model: type[BaseModel]) -> SettingsTemplate:
        """One entry per field, so new settings are included automatically.

        A field holding a model is a section, and its fields are the section's
        entries.
        """
        return SettingsTemplate(tuple(template_entries(settings_model, None)))


def template_entries(
    settings_model: type[BaseModel], section: SettingName | None
) -> list[TemplateEntry]:
    entries: list[TemplateEntry] = []
    for name, field in settings_model.model_fields.items():
        section_model = section_model_of(field)
        if section_model is not None:
            entries.extend(template_entries(section_model, SettingName(name)))
            continue
        default = (
            None
            if field.is_required()
            else TypeAdapter(field.annotation).dump_python(
                field.get_default(call_default_factory=True), mode="json"
            )
        )
        entries.append(
            TemplateEntry(
                name=SettingName(name),
                section=section,
                description=None
                if field.description is None
                else SettingDescription(field.description),
                default=None if default is None else SettingDefault(default),
            )
        )
    return entries


def section_model_of(field: FieldInfo) -> type[BaseModel] | None:
    """The model a field holds, ignoring `| None`. Root models are plain values."""
    for candidate in (field.annotation, *get_args(field.annotation)):
        if (
            isinstance(candidate, type)
            and issubclass(candidate, BaseModel)
            and not issubclass(candidate, RootModel)
        ):
            return candidate
    return None
