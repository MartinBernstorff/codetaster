import logging

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CodetasterSources
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.domain_model.vscode_extension import (
    AllowlistUpdate,
    ArgvFileError,
    BuiltExtension,
    ExtensionPackageError,
)
from codetaster.domain.secondary_ports.command_line_tools import CommandLineTools
from codetaster.domain.secondary_ports.extension_build import ExtensionBuild
from codetaster.domain.secondary_ports.proposed_api_allowlist import (
    ProposedApiAllowlist,
)
from codetaster.domain.secondary_ports.vscode_extensions import VsCodeExtensions


def install_codetaster(
    command_line_tools: CommandLineTools,
    build: ExtensionBuild,
    allowlist: ProposedApiAllowlist,
    vscode: VsCodeExtensions,
    sources: CodetasterSources,
) -> Result[BuiltExtension, ToolError | ExtensionPackageError | ArgvFileError]:
    """Install the CLI from `sources`, then build and install the extension from it.

    The extension runs the installed CLI, so both are installed together: an
    extension installed on its own can call a CLI that is out of date with it.

    The forked extension uses proposed VS Code APIs, which VS Code only enables
    for allowlisted extensions, so this also adds the extension to the
    allowlist. Every step is idempotent. Stops at the first step that fails.
    """
    log = logging.getLogger(__name__)
    log.info("Installing the codetaster CLI from %s", sources.cli_package)
    if isinstance(
        cli_installed := command_line_tools.install_command_line_tool(
            sources.cli_package
        ),
        Err,
    ):
        return cli_installed
    log.info("Building the VS Code extension")
    match build.build_extension_package(sources.checkout):
        case Err() as failed:
            return failed
        case Ok(built):
            pass
    match allowlist.allow_proposed_api(built.extension_id):
        case Err() as failed:
            return failed
        case Ok(update) if update is AllowlistUpdate.ADDED:
            log.info("Allowed %s to use proposed VS Code APIs", built.extension_id)
        case Ok():
            pass
    log.info("Installing %s", built.package)
    if isinstance(installed := vscode.install_extension_package(built.package), Err):
        return installed
    log.info(
        "Installed the codetaster CLI and %s. Restart VS Code to load it.",
        built.extension_id,
    )
    return Ok(built)
