from safe_result import Err, Ok

from codetaster.domain.application_services.install_vscode_extension import (
    install_vscode_extension,
)
from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolFailedError
from codetaster.domain.domain_model.vscode_extension import (
    ArgvFileError,
    BuiltExtension,
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


def test_installs_the_built_extension_and_allows_its_proposed_apis() -> None:
    checkout = CheckoutPath.fake()
    built = BuiltExtension.fake()
    build = FakeExtensionBuild(built)
    allowlist = InMemoryProposedApiAllowlist()
    vscode = fake_vscode_for(built)

    result = install_vscode_extension(build, allowlist, vscode, checkout)

    assert result == Ok(built)
    assert checkout in build.built_in
    assert built.extension_id in allowlist.allowed
    assert built.extension_id in vscode.installed


def test_reinstalling_succeeds() -> None:
    built = BuiltExtension.fake()
    allowlist = InMemoryProposedApiAllowlist()
    vscode = fake_vscode_for(built)

    first = install_vscode_extension(
        FakeExtensionBuild(built), allowlist, vscode, CheckoutPath.fake()
    )
    second = install_vscode_extension(
        FakeExtensionBuild(built), allowlist, vscode, CheckoutPath.fake()
    )

    assert first == second == Ok(built)
    assert allowlist.allowed == {built.extension_id}
    assert vscode.installed == {built.extension_id}


def test_a_failed_build_installs_nothing() -> None:
    failure = ToolFailedError.fake()
    built = BuiltExtension.fake()
    allowlist = InMemoryProposedApiAllowlist()
    vscode = fake_vscode_for(built)

    result = install_vscode_extension(
        FakeExtensionBuild(built, failure), allowlist, vscode, CheckoutPath.fake()
    )

    assert result == Err(failure)
    assert not allowlist.allowed
    assert not vscode.installed


def test_an_unwritable_allowlist_installs_nothing() -> None:
    failure = ArgvFileError.fake()
    built = BuiltExtension.fake()
    vscode = fake_vscode_for(built)

    result = install_vscode_extension(
        FakeExtensionBuild(built),
        InMemoryProposedApiAllowlist(failure),
        vscode,
        CheckoutPath.fake(),
    )

    assert result == Err(failure)
    assert not vscode.installed


def test_a_failed_install_is_returned() -> None:
    failure = ToolFailedError.fake()
    built = BuiltExtension.fake()

    result = install_vscode_extension(
        FakeExtensionBuild(built),
        InMemoryProposedApiAllowlist(),
        FakeVsCodeExtensions({built.package: built.extension_id}, failure=failure),
        CheckoutPath.fake(),
    )

    assert result == Err(failure)
