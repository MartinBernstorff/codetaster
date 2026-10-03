from codetaster_cli.domain.domain_model.command import CommandError


class ProtoNotInstalledError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "proto is not installed, or not on PATH. Install it with the "
            "instructions at https://moonrepo.dev/docs/proto/install, open a new "
            "shell, then re-run `uv run codetaster-cli setup`."
        )


type SetupError = ProtoNotInstalledError | CommandError
