"""Contract for CommandLineTools, run against every implementation.

The uv implementation installs into a sandbox, never into the user's tools.
"""

from pathlib import Path
from typing import Protocol, override

import pytest
from safe_result import Err, Ok

from codetaster.domain.domain_model.command_line_tool import (
    CommandName,
    CommandNames,
    PythonPackagePath,
)
from codetaster.domain.secondary_ports.command_line_tools import CommandLineTools
from codetaster.infrastructure.command_line_tools.fake_command_line_tools import (
    FakeCommandLineTools,
)
from codetaster.infrastructure.command_line_tools.test_packages import (
    PrintedText,
    write_minimal_python_package,
)
from codetaster.infrastructure.command_line_tools.uv_command_line_tools import (
    UvCommandLineTools,
    UvToolSandbox,
)


@pytest.fixture
def command() -> CommandName:
    return CommandName("codetaster-contract-probe")


@pytest.fixture
def package(tmp_path: Path, command: CommandName) -> PythonPackagePath:
    (tmp_path / "probe").mkdir()
    return write_minimal_python_package(
        PythonPackagePath(tmp_path / "probe"), command, PrintedText.fake()
    )


class InstalledTools(Protocol):
    """Somewhere tests install into through `tools`."""

    tools: CommandLineTools

    def installed_commands(self) -> CommandNames: ...


class SandboxedUvTools(InstalledTools):
    def __init__(self, sandbox: UvToolSandbox) -> None:
        self.sandbox = sandbox
        self.tools = UvCommandLineTools(sandbox)

    @override
    def installed_commands(self) -> CommandNames:
        executables = self.sandbox.executables_directory().root
        if not executables.exists():
            return CommandNames(frozenset())
        return CommandNames(
            frozenset(CommandName(each.name) for each in executables.iterdir())
        )


class FakeInstalledTools(InstalledTools):
    def __init__(self, fake: FakeCommandLineTools) -> None:
        self.fake = fake
        self.tools = fake

    @override
    def installed_commands(self) -> CommandNames:
        return CommandNames(frozenset(self.fake.installed))


@pytest.fixture(params=["uv", "fake"])
def installed(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    package: PythonPackagePath,
    command: CommandName,
) -> InstalledTools:
    if request.param == "uv":
        return SandboxedUvTools(UvToolSandbox(tmp_path / "uv-tools"))
    return FakeInstalledTools(
        FakeCommandLineTools({package: CommandNames(frozenset({command}))})
    )


def test_an_installed_package_provides_its_commands(
    installed: InstalledTools, package: PythonPackagePath, command: CommandName
) -> None:
    result = installed.tools.install_command_line_tool(package)

    assert result == Ok(None)
    assert command in installed.installed_commands().root


def test_reinstalling_the_same_package_succeeds(
    installed: InstalledTools, package: PythonPackagePath
) -> None:
    assert installed.tools.install_command_line_tool(package) == Ok(None)
    assert installed.tools.install_command_line_tool(package) == Ok(None)


def test_installing_a_missing_package_fails(
    installed: InstalledTools, tmp_path: Path
) -> None:
    missing = PythonPackagePath(tmp_path / "missing")

    assert isinstance(installed.tools.install_command_line_tool(missing), Err)
