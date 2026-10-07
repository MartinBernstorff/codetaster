import logging

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.domain_model.vscode_extension import (
    AllowlistUpdate,
    ArgvFileError,
    BuiltExtension,
    ExtensionPackageError,
)
from codetaster.domain.secondary_ports.extension_build import ExtensionBuild
from codetaster.domain.secondary_ports.proposed_api_allowlist import (
    ProposedApiAllowlist,
)
from codetaster.domain.secondary_ports.vscode_extensions import VsCodeExtensions


def install_vscode_extension(
    build: ExtensionBuild,
    allowlist: ProposedApiAllowlist,
    vscode: VsCodeExtensions,
    checkout: CheckoutPath,
) -> Result[BuiltExtension, ToolError | ExtensionPackageError | ArgvFileError]:
    """Build the forked extension in `checkout` and install it into VS Code.

    The fork uses proposed VS Code APIs, which VS Code only enables for allowlisted
    extensions, so this also adds the extension to the allowlist. Every step is
    idempotent. Stops at the first step that fails.
    """
    log = logging.getLogger(__name__)
    log.info("Building the VS Code extension")
    match build.build_extension_package(checkout):
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
    log.info("Installed %s. Restart VS Code to load it.", built.extension_id)
    return Ok(built)
