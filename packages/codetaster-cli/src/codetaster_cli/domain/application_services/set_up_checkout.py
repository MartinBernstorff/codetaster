import logging

from safe_result import Err, Ok, Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError
from codetaster_cli.domain.secondary_ports.git_hooks import GitHooks
from codetaster_cli.domain.secondary_ports.python_environment import (
    PythonEnvironment,
)
from codetaster_cli.domain.secondary_ports.toolchain import Toolchain


def set_up_checkout(
    toolchain: Toolchain,
    python_environment: PythonEnvironment,
    git_hooks: GitHooks,
    checkout: CheckoutPath,
) -> Result[CheckoutPath, ToolError]:
    """Install the pinned toolchain, the Python dependencies and the git hooks.

    Every step is idempotent, so this is safe to re-run on a checkout that is
    already set up. Stops at the first step that fails.
    """
    log = logging.getLogger(__name__)
    log.info("Installing pinned tools")
    if isinstance(installed := toolchain.install_pinned_tools(checkout), Err):
        return installed
    log.info("Syncing Python dependencies")
    if isinstance(synced := python_environment.sync_dependencies(checkout), Err):
        return synced
    log.info("Installing git hooks")
    if isinstance(hooked := git_hooks.install_hooks(checkout), Err):
        return hooked
    log.info("Checkout at %s is ready", checkout)
    return Ok(checkout)
