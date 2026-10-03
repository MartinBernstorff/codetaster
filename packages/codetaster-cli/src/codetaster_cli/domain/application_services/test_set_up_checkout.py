from safe_result import Err, Ok

from codetaster_cli.domain.application_services.set_up_checkout import set_up_checkout
from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.domain_model.command import (
    CommandFailedError,
    CommandLine,
    ExitCode,
    ProgramNotFoundError,
)
from codetaster_cli.domain.domain_model.setup_errors import ProtoNotInstalledError
from codetaster_cli.infrastructure.command_runner.fake_command_runner import (
    FakeCommandRunner,
    RecordedLines,
    ScriptedResults,
)


def test_runs_setup_steps_in_order_inside_the_checkout() -> None:
    runner = FakeCommandRunner(ScriptedResults.fake())
    checkout = CheckoutPath.fake()

    result = set_up_checkout(runner, checkout)

    assert result == Ok(checkout)
    assert runner.recorded.lines() == RecordedLines(
        [
            CommandLine(("proto", "install")),
            CommandLine(("uv", "sync", "--locked")),
            CommandLine(("uv", "run", "lefthook", "install")),
        ]
    )
    assert {command.working_directory for command in runner.recorded.root} == {
        checkout.working_directory()
    }


def test_missing_proto_explains_how_to_install_it() -> None:
    proto_install = CommandLine(("proto", "install"))
    runner = FakeCommandRunner(
        ScriptedResults({proto_install: Err(ProgramNotFoundError(proto_install))})
    )

    result = set_up_checkout(runner, CheckoutPath.fake())

    assert result == Err(ProtoNotInstalledError())
    assert "https://moonrepo.dev/docs/proto/install" in str(result.error)
    assert runner.recorded.lines() == RecordedLines([proto_install])


def test_stops_at_the_first_failing_step() -> None:
    uv_sync = CommandLine(("uv", "sync", "--locked"))
    failure = CommandFailedError(uv_sync, ExitCode(2))
    runner = FakeCommandRunner(ScriptedResults({uv_sync: Err(failure)}))

    result = set_up_checkout(runner, CheckoutPath.fake())

    assert result == Err(failure)
    assert runner.recorded.lines() == RecordedLines(
        [CommandLine(("proto", "install")), uv_sync]
    )
