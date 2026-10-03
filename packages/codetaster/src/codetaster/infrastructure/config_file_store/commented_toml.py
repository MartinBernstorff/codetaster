import tomli_w

from codetaster.domain.domain_model.configuration.template import (
    SettingsTemplate,
    TemplateEntry,
)
from codetaster.infrastructure.config_file_store.toml_parsing import FileContent


def render_commented_template(template: SettingsTemplate) -> FileContent:
    """Each setting as a commented-out TOML assignment of its default.

    A setting's description becomes comment lines above it. Top-level settings
    come first, then each section under its commented-out `[section]` header. As
    written, the file sets nothing; uncommenting an assignment, and its section
    header, sets that setting to its default.
    """
    sections = list(dict.fromkeys(entry.section for entry in template.root))
    # TOML puts every assignment after a header into that header's table.
    sections.sort(key=lambda section: section is not None)
    blocks: list[str] = []
    for section in sections:
        if section is not None:
            blocks.append(f"# [{section.root}]\n")
        blocks.extend(
            render_commented_entry(entry).root
            for entry in template.root
            if entry.section == section
        )
    return FileContent("\n".join(blocks))


def render_commented_entry(entry: TemplateEntry) -> FileContent:
    name = entry.name.root
    lines: list[str] = []
    if entry.description is not None:
        lines.extend(entry.description.root.splitlines())
    if entry.default is None:
        lines.append(f"{name} has no default.")
    else:
        lines.extend(tomli_w.dumps({name: entry.default.root}).splitlines())
    return FileContent("".join(f"# {line}\n" for line in lines))
