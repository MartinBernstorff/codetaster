from safe_result import Err, Ok

from codetaster.domain.application_services.install_codetaster import (
    install_codetaster,
)
from codetaster.domain.domain_model.checkout import CodetasterSources
from codetaster.domain.domain_model.command_line_tool import CommandNames
from codetaster.domain.domain_model.tool_errors import ToolFailedError
from codetaster.domain.domain_model.vscode_extension import (
    ArgvFileError,
    BuiltExtension,
)
from codetaster.infrastructure.command_line_tools.fake_command_line_tools import (
    FakeCommandLineTools,
)
from codetaster.infrastructure.extension_build.fake_extension_build import (
    FakeExtensionBuild,
)
from codetaster.infrastructure.proposed_api_allowlist.in_memory_allowlist import (
    InMemoryProposedApiAllowlist,
)
from codetaster.infrastructure.vscode_extensions.fake_vscode_extensions import (
    FakeVsCodeExtensions,
)


def fake_vscode_for(built: BuiltExtension) -> FakeVsCodeExtensions:
    return FakeVsCodeExtensions({built.package: built.extension_id})


def fake_tools_for(
    sources: CodetasterSources, commands: CommandNames
) -> FakeCommandLineTools:
    return FakeCommandLineTools({sources.cli_package: commands})


def test_installs_the_cli_and_the_extension_and_allows_its_proposed_apis() -> None:
    sources = CodetasterSources.fake()
    commands = CommandNames.fake()
    tools = fake_tools_for(sources, commands)
    built = BuiltExtension.fake()
    build = FakeExtensionBuild(built)
    allowlist = InMemoryProposedApiAllowlist()
    vscode = fake_vscode_for(built)

    result = install_codetaster(tools, build, allowlist, vscode, sources)

    assert result == Ok(built)
    assert tools.installed == commands.root
    assert sources.checkout in build.built_in
    assert built.extension_id in allowlist.allowed
    assert built.extension_id in vscode.installed


def test_reinstalling_succeeds() -> None:
    sources = CodetasterSources.fake()
    commands = CommandNames.fake()
    tools = fake_tools_for(sources, commands)
    built = BuiltExtension.fake()
    allowlist = InMemoryProposedApiAllowlist()
    vscode = fake_vscode_for(built)

    first = install_codetaster(
        tools,
        FakeExtensionBuild(built),
        allowlist,
        vscode,
        sources,
    )
    second = install_codetaster(
        tools,
        FakeExtensionBuild(built),
        allowlist,
        vscode,
        sources,
    )

    assert first == second == Ok(built)
    assert tools.installed == commands.root
    assert allowlist.allowed == {built.extension_id}
    assert vscode.installed == {built.extension_id}


def test_a_failed_cli_install_installs_no_extension() -> None:
    failure = ToolFailedError.fake()
    built = BuiltExtension.fake()
    build = FakeExtensionBuild(built)
    allowlist = InMemoryProposedApiAllowlist()
    vscode = fake_vscode_for(built)

    result = install_codetaster(
        FakeCommandLineTools({}, failure=failure),
        build,
        allowlist,
        vscode,
        CodetasterSources.fake(),
    )

    assert result == Err(failure)
    assert not build.built_in
    assert not allowlist.allowed
    assert not vscode.installed


def test_a_failed_build_installs_no_extension() -> None:
    failure = ToolFailedError.fake()
    sources = CodetasterSources.fake()
    built = BuiltExtension.fake()
    allowlist = InMemoryProposedApiAllowlist()
    vscode = fake_vscode_for(built)

    result = install_codetaster(
        fake_tools_for(sources, CommandNames.fake()),
        FakeExtensionBuild(built, failure),
        allowlist,
        vscode,
        sources,
    )

    assert result == Err(failure)
    assert not allowlist.allowed
    assert not vscode.installed


def test_an_unwritable_allowlist_installs_no_extension() -> None:
    failure = ArgvFileError.fake()
    sources = CodetasterSources.fake()
    built = BuiltExtension.fake()
    vscode = fake_vscode_for(built)

    result = install_codetaster(
        fake_tools_for(sources, CommandNames.fake()),
        FakeExtensionBuild(built),
        InMemoryProposedApiAllowlist(failure),
        vscode,
        sources,
    )

    assert result == Err(failure)
    assert not vscode.installed


def test_a_failed_extension_install_is_returned() -> None:
    failure = ToolFailedError.fake()
    sources = CodetasterSources.fake()
    built = BuiltExtension.fake()

    result = install_codetaster(
        fake_tools_for(sources, CommandNames.fake()),
        FakeExtensionBuild(built),
        InMemoryProposedApiAllowlist(),
        FakeVsCodeExtensions({built.package: built.extension_id}, failure=failure),
        sources,
    )

    assert result == Err(failure)
