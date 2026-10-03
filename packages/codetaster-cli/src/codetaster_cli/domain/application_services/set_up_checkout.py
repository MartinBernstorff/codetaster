import logging

from safe_result import Err, Ok, Result

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.command import (
    Command,
    CommandLine,
    ProgramNotFoundError,
)
from codetaster_cli.domain.domain_model.setup_errors import (
    ProtoNotInstalledError,
    SetupError,
)
from codetaster_cli.domain.secondary_ports.command_runner import CommandRunner


def set_up_checkout(
    runner: CommandRunner, checkout: CheckoutPath
) -> Result[CheckoutPath, SetupError]:
    """Install the pinned toolchain, the Python dependencies and the git hooks.

    Every step is idempotent, so this is safe to re-run on a checkout that is
    already set up.
    """
    steps = (
        CommandLine(("proto", "install")),
        CommandLine(("uv", "sync", "--locked")),
        CommandLine(("uv", "run", "lefthook", "install")),
    )
    for line in steps:
        command = Command(line=line, working_directory=checkout.working_directory())
        logging.getLogger(__name__).info("Running %s", command)
        match runner.run_command(command):
            case Err(ProgramNotFoundError()) if line.root[0] == "proto":
                return Err(ProtoNotInstalledError())
            case Err(error):
                return Err(error)
            case Ok():
                pass
    logging.getLogger(__name__).info("Checkout at %s is ready", checkout)
    return Ok(checkout)
