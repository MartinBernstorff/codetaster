"""Contract for ConfigFileWriter, run against every implementation."""

from collections.abc import Callable, Iterable
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
from codetaster.domain.secondary_ports.config_file_writer import ConfigFileWriter
from codetaster.infrastructure.config_file_reader.toml_parsing import (
    FileContent,
    parse_toml_document,
)
from codetaster.infrastructure.config_file_writer.in_memory import (
    InMemoryConfigFileWriter,
)
from codetaster.infrastructure.config_file_writer.local import LocalConfigFileWriter


@dataclass(frozen=True)
class WriterUnderTest:
    writer: ConfigFileWriter
    read_back: Callable[[Location], FileContent]


class WriterFactory(Protocol):
    def __call__(self, directories: Iterable[Location] = ()) -> WriterUnderTest: ...


def build_local_writer(directories: Iterable[Location] = ()) -> WriterUnderTest:
    for directory in directories:
        directory.root.mkdir(parents=True, exist_ok=True)
    return WriterUnderTest(
        writer=LocalConfigFileWriter(),
        read_back=lambda location: FileContent(
            location.root.read_text(encoding="utf-8")
        ),
    )


def build_in_memory_writer(directories: Iterable[Location] = ()) -> WriterUnderTest:
    writer = InMemoryConfigFileWriter(directories)
    return WriterUnderTest(writer=writer, read_back=writer.written.__getitem__)


@pytest.fixture(params=["local", "in_memory"])
def build_writer(request: pytest.FixtureRequest) -> WriterFactory:
    return build_local_writer if request.param == "local" else build_in_memory_writer


@pytest.fixture
def location(tmp_path: Path) -> Location:
    return Location(tmp_path).joinpath(PathName.fake())


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
    """Uncomment each assignment, including the lines of a multi-line value.

    An assignment runs from its `# <name> = ` line to the end of its block.
    """
    assignments = tuple(f"# {entry.name.root} = " for entry in template.root)
    lines: list[str] = []
    in_assignment = False
    for line in content.root.splitlines():
        in_assignment = line.startswith(assignments) or (in_assignment and line != "")
        lines.append(line.removeprefix("# ") if in_assignment else line)
    return FileContent("\n".join(lines))


def test_written_file_sets_nothing(
    build_writer: WriterFactory, location: Location
) -> None:
    under_test = build_writer()
    template = SettingsTemplate.fake()

    assert under_test.writer.write_template(location, template) == Ok(None)

    content = under_test.read_back(location)
    assert parse_toml_document(content, location) == Ok(ConfigDocument({}))


def test_uncommented_assignments_set_each_default(
    build_writer: WriterFactory, location: Location
) -> None:
    under_test = build_writer()
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

    _ = under_test.writer.write_template(location, template)

    uncommented = uncomment_assignments(under_test.read_back(location), template)
    assert parse_toml_document(uncommented, location) == Ok(expected)


def test_setting_without_default_is_listed_but_not_assigned(
    build_writer: WriterFactory, location: Location
) -> None:
    under_test = build_writer()
    template = template_with_defaults([None])
    name = template.root[0].name.root

    _ = under_test.writer.write_template(location, template)

    content = under_test.read_back(location)
    uncommented = uncomment_assignments(content, template)
    assert name in content.root
    assert parse_toml_document(uncommented, location) == Ok(ConfigDocument({}))


def test_description_is_a_comment(
    build_writer: WriterFactory, location: Location
) -> None:
    under_test = build_writer()
    description = SettingDescription.fake()
    template = SettingsTemplate(
        (TemplateEntry.fake().model_copy(update={"description": description}),)
    )

    _ = under_test.writer.write_template(location, template)

    assert f"# {description.root}" in under_test.read_back(location).root


def test_creates_missing_parent_directories(
    build_writer: WriterFactory, location: Location
) -> None:
    under_test = build_writer()
    nested = location.joinpath(PathName.fake())

    assert under_test.writer.write_template(nested, SettingsTemplate.fake()) == Ok(None)


def test_writing_over_a_directory_is_an_error_naming_it(
    build_writer: WriterFactory, location: Location
) -> None:
    under_test = build_writer([location])

    match under_test.writer.write_template(location, SettingsTemplate.fake()):
        case Err(error):
            assert error.location == location
        case Ok(value):
            pytest.fail(f"expected an error, got {value!r}")


def test_replaces_an_existing_file(
    build_writer: WriterFactory, location: Location
) -> None:
    under_test = build_writer()
    replacement = template_with_defaults([None])
    _ = under_test.writer.write_template(location, SettingsTemplate.fake())

    _ = under_test.writer.write_template(location, replacement)

    uncommented = uncomment_assignments(under_test.read_back(location), replacement)
    assert parse_toml_document(uncommented, location) == Ok(ConfigDocument({}))
