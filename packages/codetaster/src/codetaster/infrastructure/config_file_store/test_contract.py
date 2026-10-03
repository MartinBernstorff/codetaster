"""Contract for ConfigFileStore, run against every implementation."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pytest
from safe_result import Err, Ok

from codetaster.domain.domain_model.configuration.document import ConfigDocument
from codetaster.domain.domain_model.configuration.template import (
    SettingDefault,
    SettingDescription,
    SettingName,
    SettingsTemplate,
    TemplateEntry,
)
from codetaster.domain.domain_model.filesystem import Location, PathName
from codetaster.domain.secondary_ports.config_file_store import ConfigFileStore
from codetaster.infrastructure.config_file_store.in_memory import (
    InMemoryConfigFileStore,
)
from codetaster.infrastructure.config_file_store.local import LocalConfigFileStore
from codetaster.infrastructure.config_file_store.toml_parsing import (
    FileContent,
    parse_toml_document,
)


@dataclass(frozen=True)
class StoreUnderTest:
    store: ConfigFileStore
    read_back: Callable[[Location], FileContent]


class StoreFactory(Protocol):
    def __call__(
        self,
        files: Mapping[Location, FileContent],
        directories: Iterable[Location] = (),
    ) -> StoreUnderTest: ...


def build_local_store(
    files: Mapping[Location, FileContent], directories: Iterable[Location] = ()
) -> StoreUnderTest:
    for location, content in files.items():
        location.root.parent.mkdir(parents=True, exist_ok=True)
        _ = location.root.write_text(content.root, encoding="utf-8")
    for directory in directories:
        directory.root.mkdir(parents=True, exist_ok=True)
    return StoreUnderTest(
        store=LocalConfigFileStore(),
        read_back=lambda location: FileContent(
            location.root.read_text(encoding="utf-8")
        ),
    )


def build_in_memory_store(
    files: Mapping[Location, FileContent], directories: Iterable[Location] = ()
) -> StoreUnderTest:
    store = InMemoryConfigFileStore(files, directories)
    return StoreUnderTest(store=store, read_back=store.files.__getitem__)


@pytest.fixture(params=["local", "in_memory"])
def build_store(request: pytest.FixtureRequest) -> StoreFactory:
    return build_local_store if request.param == "local" else build_in_memory_store


@pytest.fixture
def root(tmp_path: Path) -> Location:
    return Location(tmp_path)


@pytest.fixture
def location(root: Location) -> Location:
    return root.joinpath(PathName.fake())


def test_missing_file_is_none(build_store: StoreFactory, root: Location) -> None:
    store = build_store({}).store

    assert store.read_document(root.joinpath(PathName.fake())) == Ok(None)


def test_reads_toml_document(build_store: StoreFactory, root: Location) -> None:
    location = root.joinpath(PathName.fake())
    key = "log_format"
    value = "json"
    store = build_store({location: FileContent(f'{key} = "{value}"\n')}).store

    assert store.read_document(location) == Ok(ConfigDocument({key: value}))


def test_malformed_toml_is_an_error_naming_the_file(
    build_store: StoreFactory, root: Location
) -> None:
    location = root.joinpath(PathName.fake())
    expected_reason = "invalid TOML"
    store = build_store({location: FileContent("log_format = \n")}).store

    match store.read_document(location):
        case Err(error):
            assert error.location == location
            assert expected_reason in error.reason.root
        case Ok(value):
            pytest.fail(f"expected an error, got {value!r}")


def test_reading_a_directory_is_an_error(
    build_store: StoreFactory, root: Location
) -> None:
    directory = root.joinpath(PathName.fake())
    store = build_store({}, [directory]).store

    assert isinstance(store.read_document(directory), Err)


def test_exists_for_files_and_directories(
    build_store: StoreFactory, root: Location
) -> None:
    file = root.joinpath(PathName("file"))
    directory = root.joinpath(PathName("directory"))
    store = build_store({file: FileContent.fake()}, [directory]).store

    assert store.exists(file)
    assert store.exists(directory)
    assert not store.exists(root.joinpath(PathName("absent")))


def template_with_defaults(
    defaults: Iterable[SettingDefault | None],
) -> SettingsTemplate:
    return SettingsTemplate(
        tuple(
            TemplateEntry.fake().model_copy(
                update={"name": SettingName(f"setting_{index}"), "default": default}
            )
            for index, default in enumerate(defaults)
        )
    )


def uncomment_assignments(
    content: FileContent, template: SettingsTemplate
) -> FileContent:
    """Uncomment each section header and assignment, including multi-line values.

    An assignment runs from its `# <name> = ` line to the end of its block.
    """
    assignments = tuple(f"# {entry.name.root} = " for entry in template.root) + tuple(
        f"# [{entry.section.root}]" for entry in template.root if entry.section
    )
    lines: list[str] = []
    in_assignment = False
    for line in content.root.splitlines():
        in_assignment = line.startswith(assignments) or (in_assignment and line != "")
        lines.append(line.removeprefix("# ") if in_assignment else line)
    return FileContent("\n".join(lines))


def test_written_file_sets_nothing(
    build_store: StoreFactory, location: Location
) -> None:
    under_test = build_store({})
    template = SettingsTemplate.fake()

    assert under_test.store.write_template(location, template) == Ok(None)

    assert under_test.store.read_document(location) == Ok(ConfigDocument({}))


def test_uncommented_assignments_set_each_default(
    build_store: StoreFactory, location: Location
) -> None:
    under_test = build_store({})
    defaults = [
        SettingDefault("text"),
        SettingDefault(3),
        SettingDefault(root=True),
        SettingDefault(["a", "b"]),
    ]
    template = template_with_defaults(defaults)
    expected = ConfigDocument(
        {
            entry.name.root: entry.default.root
            for entry in template.root
            if entry.default
        }
    )

    _ = under_test.store.write_template(location, template)

    uncommented = uncomment_assignments(under_test.read_back(location), template)
    assert parse_toml_document(uncommented, location) == Ok(expected)


def test_setting_without_default_is_listed_but_not_assigned(
    build_store: StoreFactory, location: Location
) -> None:
    under_test = build_store({})
    template = template_with_defaults([None])
    name = template.root[0].name.root

    _ = under_test.store.write_template(location, template)

    content = under_test.read_back(location)
    uncommented = uncomment_assignments(content, template)
    assert name in content.root
    assert parse_toml_document(uncommented, location) == Ok(ConfigDocument({}))


def test_description_is_a_comment(
    build_store: StoreFactory, location: Location
) -> None:
    under_test = build_store({})
    description = SettingDescription.fake()
    template = SettingsTemplate(
        (TemplateEntry.fake().model_copy(update={"description": description}),)
    )

    _ = under_test.store.write_template(location, template)

    assert f"# {description.root}" in under_test.read_back(location).root


def test_creates_missing_parent_directories(
    build_store: StoreFactory, location: Location
) -> None:
    under_test = build_store({})
    nested = location.joinpath(PathName.fake())

    assert under_test.store.write_template(nested, SettingsTemplate.fake()) == Ok(None)


def test_writing_over_a_directory_is_an_error_naming_it(
    build_store: StoreFactory, location: Location
) -> None:
    under_test = build_store({}, [location])

    match under_test.store.write_template(location, SettingsTemplate.fake()):
        case Err(error):
            assert error.location == location
        case Ok(value):
            pytest.fail(f"expected an error, got {value!r}")


def test_replaces_an_existing_file(
    build_store: StoreFactory, location: Location
) -> None:
    under_test = build_store({})
    replacement = template_with_defaults([None])
    _ = under_test.store.write_template(location, SettingsTemplate.fake())

    _ = under_test.store.write_template(location, replacement)

    uncommented = uncomment_assignments(under_test.read_back(location), replacement)
    assert parse_toml_document(uncommented, location) == Ok(ConfigDocument({}))


def test_section_settings_are_set_under_their_section(
    build_store: StoreFactory, location: Location
) -> None:
    under_test = build_store({})
    section = SettingName("review")
    top_level = TemplateEntry.fake()
    in_section = TemplateEntry.fake().model_copy(update={"section": section})
    template = SettingsTemplate((in_section, top_level))
    assert top_level.default is not None
    assert in_section.default is not None
    expected = ConfigDocument(
        {
            top_level.name.root: top_level.default.root,
            section.root: {in_section.name.root: in_section.default.root},
        }
    )

    _ = under_test.store.write_template(location, template)

    uncommented = uncomment_assignments(under_test.read_back(location), template)
    assert parse_toml_document(uncommented, location) == Ok(expected)
