"""Contract for VsCodeExtensions, run against every implementation.

The `code` implementation runs in a sandbox, never against the user's VS Code, and
is skipped where VS Code is not installed (as in CI).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Protocol, override

import pytest
from safe_result import Err, Ok

from codetaster.domain.domain_model.vscode_extension import (
    ExtensionId,
    ExtensionIds,
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


class VsCode(Protocol):
    """A VS Code that tests install into through `extensions`."""

    extensions: VsCodeExtensions

    def installed_extensions(self) -> ExtensionIds: ...


class SandboxedVsCode(VsCode):
    def __init__(self, sandbox: VsCodeSandbox) -> None:
        self.sandbox = sandbox
        self.extensions = CodeCliExtensions(sandbox)

    @override
    def installed_extensions(self) -> ExtensionIds:
        listed = subprocess.run(
            ["code", *self.sandbox.arguments().root, "--list-extensions"],
            check=True,
            capture_output=True,
            text=True,
        )
        return ExtensionIds(
            frozenset(
                ExtensionId(line.strip())
                for line in listed.stdout.splitlines()
                if line.strip()
            )
        )


class FakeVsCode(VsCode):
    def __init__(self, fake: FakeVsCodeExtensions) -> None:
        self.fake = fake
        self.extensions = fake

    @override
    def installed_extensions(self) -> ExtensionIds:
        return ExtensionIds(frozenset(self.fake.installed))


@pytest.fixture(params=["code", "fake"])
def vscode(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    package: ExtensionPackagePath,
    extension: ExtensionId,
) -> VsCode:
    if request.param == "code":
        if shutil.which("code") is None:
            pytest.skip("the `code` CLI is not installed")
        return SandboxedVsCode(VsCodeSandbox(tmp_path / "vscode"))
    return FakeVsCode(FakeVsCodeExtensions({package: extension}))


def test_an_installed_package_is_listed(
    vscode: VsCode, package: ExtensionPackagePath, extension: ExtensionId
) -> None:
    installed = vscode.extensions.install_extension_package(package)

    assert installed == Ok(None)
    assert extension.normalised() in vscode.installed_extensions().normalised().root


def test_reinstalling_the_same_package_succeeds(
    vscode: VsCode, package: ExtensionPackagePath
) -> None:
    assert vscode.extensions.install_extension_package(package) == Ok(None)
    assert vscode.extensions.install_extension_package(package) == Ok(None)


def test_installing_a_missing_package_fails(vscode: VsCode, tmp_path: Path) -> None:
    missing = ExtensionPackagePath(tmp_path / "missing.vsix")

    assert isinstance(vscode.extensions.install_extension_package(missing), Err)
