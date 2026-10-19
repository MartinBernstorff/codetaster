from pydantic import ConfigDict, RootModel

from codetaster.domain.domain_model.command_line_tool import (
    CommandName,
    PythonPackagePath,
)


class PrintedText(RootModel[str]):
    """What a probe command prints when run."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> PrintedText:
        return PrintedText("probe")


def write_minimal_python_package(
    package: PythonPackagePath, command: CommandName, printed: PrintedText
) -> PythonPackagePath:
    """Write a package whose one command, `command`, prints `printed`.

    Rewriting it with other text changes the code but not the version, as editing
    a checkout does.
    """
    module = command.root.replace("-", "_")
    (package.root / "src" / module).mkdir(parents=True, exist_ok=True)
    _ = (package.root / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{command.root}"\n'
        'version = "0"\n'
        'requires-python = ">=3.14"\n'
        "[project.scripts]\n"
        f'{command.root} = "{module}:main"\n'
        "[build-system]\n"
        'requires = ["uv_build>=0.9,<0.10"]\n'
        'build-backend = "uv_build"\n'
    )
    _ = (package.root / "src" / module / "__init__.py").write_text(
        f"def main() -> None:\n    print({printed.root!r})\n"
    )
    return package
