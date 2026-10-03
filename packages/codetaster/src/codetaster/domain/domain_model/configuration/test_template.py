from codetaster.domain.domain_model.configuration.settings import Settings
from codetaster.domain.domain_model.configuration.template import (
    SettingDefault,
    SettingName,
    SettingsTemplate,
)


def test_has_one_entry_per_setting_with_its_default() -> None:
    defaults = Settings().model_dump(mode="json")
    expected = {
        SettingName(name): SettingDefault(value) for name, value in defaults.items()
    }

    template = SettingsTemplate.from_settings_schema()

    assert {entry.name: entry.default for entry in template.root} == expected


def test_carries_each_setting_description() -> None:
    expected = {
        SettingName(name): field.description
        for name, field in Settings.model_fields.items()
    }

    template = SettingsTemplate.from_settings_schema()

    assert {
        entry.name: None if entry.description is None else entry.description.root
        for entry in template.root
    } == expected
