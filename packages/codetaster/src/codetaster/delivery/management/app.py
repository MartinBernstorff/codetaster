import logging
from pathlib import Path
from typing import Annotated

import typer
from safe_result import Err, Ok, Result

from codetaster.domain.application_services.install_vscode_extension import (
    install_vscode_extension,
)
from codetaster.domain.application_services.set_up_checkout import set_up_checkout
from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.filesystem import Location
from codetaster.infrastructure.extension_build.moon_extension_build import (
    MoonExtensionBuild,
    MoonTarget,
)
from codetaster.infrastructure.git_hooks.lefthook_git_hooks import (
    LefthookGitHooks,
)
from codetaster.infrastructure.proposed_api_allowlist.argv_json_allowlist import (
    ArgvJsonAllowlist,
)
from codetaster.infrastructure.python_environment.uv_python_environment import (
    UvPythonEnvironment,
)
from codetaster.infrastructure.toolchain.proto_toolchain import ProtoToolchain
from codetaster.infrastructure.vscode_extensions.code_cli_extensions import (
    CodeCliExtensions,
)

app = typer.Typer(
    no_args_is_help=True, help="Management commands for working on codetaster."
)


@app.callback()
def configure_logging(
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Only log warnings and errors.")
    ] = False,
) -> None:
    logging.basicConfig(
        level=logging.WARNING if quiet else logging.INFO, format="%(message)s"
    )


@app.command()
def setup() -> None:
    """Make the current checkout ready to work in.

    Runs `proto install`, `uv sync --locked` and `uv run lefthook install`.
    Safe to re-run.
    """
    _ = exit_on_error(
        set_up_checkout(
            ProtoToolchain(),
            UvPythonEnvironment(),
            LefthookGitHooks(),
            CheckoutPath(Path.cwd()),
        )
    )


@app.command()
def install_extension() -> None:
    """Build the forked GitHub Pull Requests extension and install it into VS Code.

    Builds the VSIX with `moon run vscode-extension:package`, adds the extension to
    `enable-proposed-api` in `~/.vscode/argv.json` and installs it with `code`.
    Restart VS Code afterwards. Safe to re-run.
    """
    _ = exit_on_error(
        install_vscode_extension(
            MoonExtensionBuild(MoonTarget("vscode-extension:package")),
            ArgvJsonAllowlist(Location(Path.home() / ".vscode" / "argv.json")),
            CodeCliExtensions(),
            CheckoutPath(Path.cwd()),
        )
    )


@app.command()
def teardown() -> None:
    """Clean up before the current checkout is deleted.

    Deleting a worktree already removes its virtualenv and task cache, and the git
    hooks are shared with the other checkouts, so there is nothing to do yet. Add
    steps here for state that lives outside the checkout.
    """
    logging.getLogger(__name__).info("Nothing to tear down")


def exit_on_error[T](result: Result[T, Exception]) -> T:
    """Turn an error result into a message on stderr and exit code 1."""
    match result:
        case Ok(value):
            return value
        case Err(error):
            logging.getLogger(__name__).error("%s", error)
            raise typer.Exit(code=1)
