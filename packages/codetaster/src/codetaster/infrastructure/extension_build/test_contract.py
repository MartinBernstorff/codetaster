"""Contract for ExtensionBuild, run against every implementation.

The moon implementation runs against a throwaway moon workspace whose package task
copies a prebuilt `.vsix`, so the real extension is not built here.
"""

import os
import subprocess
from pathlib import Path

import pytest
from safe_result import Ok

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.vscode_extension import (
    BuiltExtension,
    ExtensionId,
    ExtensionPackagePath,
)
from codetaster.domain.secondary_ports.extension_build import ExtensionBuild
from codetaster.infrastructure.extension_build.fake_extension_build import (
    FakeExtensionBuild,
)
from codetaster.infrastructure.extension_build.moon_extension_build import (
    MoonExtensionBuild,
    MoonTarget,
)
from codetaster.infrastructure.vscode_extensions.test_packages import (
    write_minimal_vsix,
)

PACKAGE_TASK = """\
tasks:
  package:
    script: 'cp prebuilt.vsix built.vsix'
    inputs: ['prebuilt.vsix']
    outputs: ['built.vsix']
"""


def write_moon_workspace(
    workspace: CheckoutPath, extension: ExtensionId, monkeypatch: pytest.MonkeyPatch
) -> CheckoutPath:
    """A moon workspace with one project, `ext`, whose `package` task makes a VSIX.

    Pins the moon version that runs the tests, since a temporary directory is
    outside every `.prototools`. Unsets the `MOON_*` variables a surrounding
    `moon run :test` sets, which would point moon at this repository instead.
    """
    for variable in [name for name in os.environ if name.startswith("MOON_")]:
        monkeypatch.delenv(variable)
    moon_version = subprocess.run(
        ["moon", "--version"], capture_output=True, text=True, check=True
    ).stdout.split()[-1]
    root = workspace.root
    _ = (root / ".prototools").write_text(f'moon = "{moon_version}"\n')
    (root / ".moon").mkdir()
    _ = (root / ".moon" / "workspace.yml").write_text("projects:\n  - 'ext'\n")
    (root / "ext").mkdir()
    _ = (root / "ext" / "moon.yml").write_text(PACKAGE_TASK)
    _ = write_minimal_vsix(
        ExtensionPackagePath(root / "ext" / "prebuilt.vsix"), extension
    )
    return workspace


@pytest.fixture
def extension() -> ExtensionId:
    return ExtensionId("codetaster-contract.probe")


@pytest.fixture
def workspace(
    tmp_path: Path, extension: ExtensionId, monkeypatch: pytest.MonkeyPatch
) -> CheckoutPath:
    return write_moon_workspace(CheckoutPath(tmp_path), extension, monkeypatch)


@pytest.fixture
def expected(workspace: CheckoutPath, extension: ExtensionId) -> BuiltExtension:
    return BuiltExtension(
        package=ExtensionPackagePath(workspace.root / "ext" / "built.vsix"),
        extension_id=extension,
    )


@pytest.fixture(params=["moon", "fake"])
def build(request: pytest.FixtureRequest, expected: BuiltExtension) -> ExtensionBuild:
    if request.param == "moon":
        return MoonExtensionBuild(MoonTarget("ext:package"))
    return FakeExtensionBuild(expected)


def test_building_returns_the_package_and_its_id(
    build: ExtensionBuild, workspace: CheckoutPath, expected: BuiltExtension
) -> None:
    assert build.build_extension_package(workspace) == Ok(expected)


def test_building_twice_succeeds(
    build: ExtensionBuild, workspace: CheckoutPath, expected: BuiltExtension
) -> None:
    assert build.build_extension_package(workspace) == Ok(expected)
    assert build.build_extension_package(workspace) == Ok(expected)
