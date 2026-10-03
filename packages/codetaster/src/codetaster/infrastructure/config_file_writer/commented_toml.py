import tomli_w

from codetaster.domain.domain_model.configuration.template import SettingsTemplate
from codetaster.infrastructure.config_file_reader.toml_parsing import FileContent


def render_commented_template(template: SettingsTemplate) -> FileContent:
    """Each setting as a commented-out TOML assignment of its default.

    A setting's description becomes comment lines above it. As written, the file
    sets nothing; uncommenting an assignment sets that setting to its default.
    """
    blocks: list[str] = []
    for entry in template.root:
        name = entry.name.root
        lines: list[str] = []
        if entry.description is not None:
            lines.extend(entry.description.root.splitlines())
        if entry.default is None:
            lines.append(f"{name} has no default.")
        else:
            lines.extend(tomli_w.dumps({name: entry.default.root}).splitlines())
        blocks.append("".join(f"# {line}\n" for line in lines))
    return FileContent("\n".join(blocks))
