from pathlib import Path

import pytest
from safe_result import Err

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolFailedError
from codetaster.domain.domain_model.vscode_extension import (
    ExtensionId,
    ExtensionPackageError,
    ExtensionPackagePath,
)
from codetaster.infrastructure.extension_build.moon_extension_build import (
    MoonExtensionBuild,
    MoonTarget,
    package_in_task_description,
    read_extension_id,
)
from codetaster.infrastructure.extension_build.test_contract import (
    write_moon_workspace,
)
from codetaster.infrastructure.external_tool.run_external_tool import ToolOutput
from codetaster.infrastructure.vscode_extensions.test_packages import (
    write_minimal_vsix,
)


def test_a_failing_task_is_a_tool_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = write_moon_workspace(
        CheckoutPath(tmp_path), ExtensionId.fake(), monkeypatch
    )

    result = MoonExtensionBuild(MoonTarget("ext:no-such-task")).build_extension_package(
        workspace
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, ToolFailedError)


def test_a_task_without_one_vsix_output_is_a_package_error() -> None:
    description = ToolOutput('{"outputFiles": {"ext/a.vsix": {}, "ext/b.vsix": {}}}')

    result = package_in_task_description(description, CheckoutPath.fake())

    assert isinstance(result, Err)
    assert isinstance(result.error, ExtensionPackageError)


def test_reads_the_id_from_the_package(tmp_path: Path) -> None:
    extension = ExtensionId.fake()
    package = write_minimal_vsix(ExtensionPackagePath(tmp_path / "x.vsix"), extension)

    assert read_extension_id(package).unwrap() == extension


def test_a_file_that_is_not_a_package_is_a_package_error(tmp_path: Path) -> None:
    not_a_package = tmp_path / "x.vsix"
    _ = not_a_package.write_text("not a zip")

    result = read_extension_id(ExtensionPackagePath(not_a_package))

    assert isinstance(result, Err)
    assert isinstance(result.error, ExtensionPackageError)
