import logging

from safe_result import Err, Ok, Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.tool_errors import ToolError
from codetaster_cli.domain.secondary_ports.git_hooks import GitHooks
from codetaster_cli.domain.secondary_ports.git_worktrees import GitWorktrees
from codetaster_cli.domain.secondary_ports.python_environment import (
    PythonEnvironment,
)
from codetaster_cli.domain.secondary_ports.task_cache import TaskCache


def tear_down_checkout(
    git_worktrees: GitWorktrees,
    git_hooks: GitHooks,
    python_environment: PythonEnvironment,
    task_cache: TaskCache,
    checkout: CheckoutPath,
) -> Result[CheckoutPath, ToolError]:
    """Undo `set_up_checkout` for this checkout.

    Git hooks live in the repository's common git directory and are shared by every
    worktree, so they are only uninstalled when this is the last checkout. The
    pinned toolchain is shared by every project on the machine and is left alone.
    """
    log = logging.getLogger(__name__)
    match git_worktrees.count_worktrees(checkout):
        case Err() as failed:
            return failed
        case Ok(worktrees):
            pass
    # The hooks tool is installed into the virtualenv, so it has to run first.
    if worktrees.is_last_checkout():
        log.info("Uninstalling git hooks")
        if isinstance(unhooked := git_hooks.uninstall_hooks(checkout), Err):
            return unhooked
    else:
        log.info("Keeping git hooks: %s other checkout(s) use them", worktrees.others())
    log.info("Removing the virtualenv")
    if isinstance(removed := python_environment.remove_virtualenv(checkout), Err):
        return removed
    log.info("Clearing the task cache")
    if isinstance(cleared := task_cache.clear_cache(checkout), Err):
        return cleared
    log.info("Checkout at %s is torn down", checkout)
    return Ok(checkout)
