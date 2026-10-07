import json
import zipfile
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
        built = run_external_tool(
            ToolArguments(("moon", "run", self.target.root)),
            checkout,
            OutputMode.SHOW,
            self.hint,
        )
        if isinstance(built, Err):
            return built
        described = run_external_tool(
            ToolArguments(("moon", "task", self.target.root, "--json")),
            checkout,
            OutputMode.CAPTURE,
            self.hint,
        )
        match described:
            case Err() as failed:
                return failed
            case Ok(description):
                pass
        match package_in_task_description(description, checkout):
            case Err() as failed:
                return failed
            case Ok(package):
                pass
        return read_extension_id(package).map(
            lambda extension_id: BuiltExtension(
                package=package, extension_id=extension_id
            )
        )


def package_in_task_description(
    description: ToolOutput, checkout: CheckoutPath
) -> Result[ExtensionPackagePath, ExtensionPackageError]:
    """The one `.vsix` among the outputs listed by `moon task --json`."""
    try:
        task = cast("dict[str, dict[str, object]]", json.loads(description.root))
        outputs = list(task["outputFiles"])
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        return Err(
            ExtensionPackageError(
                ProblemDescription(f"unexpected output from `moon task`: {error!r}")
            )
        )
    packages = [path for path in outputs if path.endswith(".vsix")]
    if len(packages) != 1:
        return Err(
            ExtensionPackageError(
                ProblemDescription(
                    f"expected the task to output one .vsix file, got {outputs}"
                )
            )
        )
    return Ok(ExtensionPackagePath(checkout.root / packages[0]))


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
