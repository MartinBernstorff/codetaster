import subprocess
from pathlib import Path

from codetaster.domain.domain_model.command_line_tool import (
    CommandName,
    PythonPackagePath,
)
from codetaster.infrastructure.command_line_tools.test_packages import (
    PrintedText,
    write_minimal_python_package,
)
from codetaster.infrastructure.command_line_tools.uv_command_line_tools import (
    UvCommandLineTools,
    UvToolSandbox,
)


def test_reinstalling_picks_up_changes_that_keep_the_version(tmp_path: Path) -> None:
    command = CommandName("codetaster-reinstall-probe")
    package = PythonPackagePath(tmp_path / "probe")
    package.root.mkdir()
    sandbox = UvToolSandbox(tmp_path / "uv-tools")
    tools = UvCommandLineTools(sandbox)
    changed = PrintedText("changed")
    _ = tools.install_command_line_tool(
        write_minimal_python_package(package, command, PrintedText("original"))
    ).unwrap()

    _ = tools.install_command_line_tool(
        write_minimal_python_package(package, command, changed)
    ).unwrap()

    ran = subprocess.run(
        [sandbox.executables_directory().root / command.root],
        capture_output=True,
        text=True,
        check=True,
    )
    assert ran.stdout.strip() == changed.root
