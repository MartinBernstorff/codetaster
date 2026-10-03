from codetaster_cli.domain.domain_model.command import Command, CommandLine
from codetaster_cli.infrastructure.command_runner.fake_command_runner import (
    FakeCommandRunner,
    RecordedLines,
    ScriptedResults,
)


def test_records_commands_in_order() -> None:
    runner = FakeCommandRunner(ScriptedResults.fake())
    first = Command.fake().model_copy(update={"line": CommandLine(("a",))})
    second = Command.fake().model_copy(update={"line": CommandLine(("b",))})

    _ = runner.run_command(first)
    _ = runner.capture_output(second)

    assert runner.recorded.lines() == RecordedLines([first.line, second.line])
