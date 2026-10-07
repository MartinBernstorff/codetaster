from codetaster.domain.domain_model.configuration.review_settings import (
    ProjectSettings,
    ReviewSettings,
)
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

    template = SettingsTemplate.from_settings_schema(Settings)

    assert {entry.name: entry.default for entry in template.root} == expected


def test_carries_each_setting_description() -> None:
    expected = {
        SettingName(name): field.description
        for name, field in Settings.model_fields.items()
    }

    template = SettingsTemplate.from_settings_schema(Settings)

    assert {
        entry.name: None if entry.description is None else entry.description.root
        for entry in template.root
    } == expected


def test_a_nested_model_is_a_section_of_its_own_settings() -> None:
    section = SettingName("review")
    expected = {SettingName(name) for name in ReviewSettings.model_fields}

    template = SettingsTemplate.from_settings_schema(ProjectSettings)

    assert {entry.name for entry in template.root if entry.section == section} == (
        expected
    )
    assert section not in {entry.name for entry in template.root}


def test_a_required_setting_has_no_default() -> None:
    required = {
        SettingName(name)
        for name, field in ReviewSettings.model_fields.items()
        if field.is_required()
    }

    template = SettingsTemplate.from_settings_schema(ReviewSettings)

    assert {entry.default for entry in template.root if entry.name in required} == {
        None
    }
