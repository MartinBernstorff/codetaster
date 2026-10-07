import json
import os
import zipfile
from pathlib import Path
from typing import cast, override

from pydantic import ConfigDict, RootModel
from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import InstallationHint, ToolError
from codetaster.domain.domain_model.vscode_extension import (
    BuiltExtension,
    ExtensionId,
    ExtensionPackageError,
    ExtensionPackagePath,
    ProblemDescription,
)
from codetaster.domain.secondary_ports.extension_build import ExtensionBuild
from codetaster.infrastructure.external_tool.run_external_tool import (
    OutputMode,
    ToolArguments,
    ToolEnvironment,
    ToolOutput,
    run_external_tool,
)


class MoonTarget(RootModel[str]):
    """A moon task, as `<project>:<task>`."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> MoonTarget:
        return MoonTarget("vscode-extension:package")


class MoonExtensionBuild(ExtensionBuild):
    """Runs the moon task `target`, which must output exactly one `.vsix` file."""

    def __init__(self, target: MoonTarget) -> None:
        self.target = target
        self.hint = InstallationHint(
            "Install proto (https://moonrepo.dev/docs/proto/install), then run "
            "`uv run codetaster-manage setup`."
        )

    @override
    def build_extension_package(
        self, checkout: CheckoutPath
    ) -> Result[BuiltExtension, ToolError | ExtensionPackageError]:
        # Variables set by a surrounding moon run, such as MOON_WORKSPACE_ROOT,
        # would make moon use that workspace instead of `checkout`'s.
        environment = ToolEnvironment(
            {
                name: value
                for name, value in os.environ.items()
                if not name.startswith("MOON_")
            }
        )
        built = run_external_tool(
            ToolArguments(("moon", "run", self.target.root)),
            checkout,
            OutputMode.SHOW,
            self.hint,
            environment,
        )
        if isinstance(built, Err):
            return built
        project, _, _ = self.target.root.partition(":")
        described = run_external_tool(
            ToolArguments(("moon", "project", project, "--json")),
            checkout,
            OutputMode.CAPTURE,
            self.hint,
            environment,
        )
        match described:
            case Err() as failed:
                return failed
            case Ok(description):
                pass
        match package_in_project_description(description, self.target):
            case Err() as failed:
                return failed
            case Ok(package):
                pass
        return read_extension_id(package).map(
            lambda extension_id: BuiltExtension(
                package=package, extension_id=extension_id
            )
        )


def package_in_project_description(
    description: ToolOutput, target: MoonTarget
) -> Result[ExtensionPackagePath, ExtensionPackageError]:
    """The one `.vsix` that `target` outputs, according to `moon project --json`.

    Task outputs are relative to the project root, which moon reports as absolute.
    """
    _, _, task_name = target.root.partition(":")
    try:
        project = cast("dict[str, object]", json.loads(description.root))
        root = Path(cast("str", project["root"]))
        tasks = cast("dict[str, dict[str, list[dict[str, str]]]]", project["tasks"])
        outputs = tasks[task_name]["outputs"]
        files = [output["file"] for output in outputs if "file" in output]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        return Err(
            ExtensionPackageError(
                ProblemDescription(f"unexpected output from `moon project`: {error!r}")
            )
        )
    packages = [file for file in files if file.endswith(".vsix")]
    if len(packages) != 1:
        return Err(
            ExtensionPackageError(
                ProblemDescription(
                    f"expected {target.root} to output one .vsix file, got {files}"
                )
            )
        )
    return Ok(ExtensionPackagePath(root / packages[0]))


def read_extension_id(
    package: ExtensionPackagePath,
) -> Result[ExtensionId, ExtensionPackageError]:
    """The `<publisher>.<name>` in the package's `extension/package.json`."""
    try:
        with zipfile.ZipFile(package.root) as archive:
            manifest = json.loads(archive.read("extension/package.json"))
        return Ok(ExtensionId(f"{manifest['publisher']}.{manifest['name']}"))
    except (OSError, zipfile.BadZipFile, KeyError, TypeError, ValueError) as error:
        return Err(
            ExtensionPackageError(
                ProblemDescription(f"cannot read the ID from {package}: {error!r}")
            )
        )
