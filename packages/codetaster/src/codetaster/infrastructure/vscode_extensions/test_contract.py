"""Contract for VsCodeExtensions, run against every implementation.

The `code` implementation runs in a sandbox, never against the user's VS Code, and
is skipped where VS Code is not installed (as in CI).
"""

import shutil
from pathlib import Path

import pytest
from safe_result import Err, Ok

from codetaster.domain.domain_model.vscode_extension import (
    ExtensionId,
    ExtensionPackagePath,
)
from codetaster.domain.secondary_ports.vscode_extensions import VsCodeExtensions
from codetaster.infrastructure.vscode_extensions.code_cli_extensions import (
    CodeCliExtensions,
    VsCodeSandbox,
)
from codetaster.infrastructure.vscode_extensions.fake_vscode_extensions import (
    FakeVsCodeExtensions,
)
from codetaster.infrastructure.vscode_extensions.test_packages import (
    write_minimal_vsix,
)


@pytest.fixture
def extension() -> ExtensionId:
    return ExtensionId("codetaster-contract.probe")


@pytest.fixture
def package(tmp_path: Path, extension: ExtensionId) -> ExtensionPackagePath:
    return write_minimal_vsix(ExtensionPackagePath(tmp_path / "probe.vsix"), extension)


@pytest.fixture(params=["code", "fake"])
def vscode(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    package: ExtensionPackagePath,
    extension: ExtensionId,
) -> VsCodeExtensions:
    if request.param == "code":
        if shutil.which("code") is None:
            pytest.skip("the `code` CLI is not installed")
        return CodeCliExtensions(VsCodeSandbox(tmp_path / "vscode"))
    return FakeVsCodeExtensions({package: extension})


def test_an_installed_package_is_listed(
    vscode: VsCodeExtensions, package: ExtensionPackagePath, extension: ExtensionId
) -> None:
    installed = vscode.install_extension_package(package)

    assert installed == Ok(None)
    listed = vscode.list_installed_extensions()
    assert isinstance(listed, Ok)
    assert listed.value.includes(extension)


def test_reinstalling_the_same_package_succeeds(
    vscode: VsCodeExtensions, package: ExtensionPackagePath
) -> None:
    assert vscode.install_extension_package(package) == Ok(None)
    assert vscode.install_extension_package(package) == Ok(None)


def test_installing_a_missing_package_fails(
    vscode: VsCodeExtensions, tmp_path: Path
) -> None:
    missing = ExtensionPackagePath(tmp_path / "missing.vsix")

    assert isinstance(vscode.install_extension_package(missing), Err)
