"""Contract for ProposedApiAllowlist, run against every implementation."""

from pathlib import Path

import pytest
from safe_result import Ok

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.vscode_extension import (
    AllowlistUpdate,
    ExtensionId,
)
from codetaster.domain.secondary_ports.proposed_api_allowlist import (
    ProposedApiAllowlist,
)
from codetaster.infrastructure.proposed_api_allowlist.argv_json_allowlist import (
    ArgvJsonAllowlist,
)
from codetaster.infrastructure.proposed_api_allowlist.in_memory_allowlist import (
    InMemoryProposedApiAllowlist,
)


@pytest.fixture(params=["argv.json", "in-memory"])
def allowlist(request: pytest.FixtureRequest, tmp_path: Path) -> ProposedApiAllowlist:
    if request.param == "argv.json":
        return ArgvJsonAllowlist(Location(tmp_path / ".vscode" / "argv.json"))
    return InMemoryProposedApiAllowlist()


def test_an_allowed_extension_is_listed(allowlist: ProposedApiAllowlist) -> None:
    extension = ExtensionId.fake()

    _ = allowlist.allow_proposed_api(extension)

    listed = allowlist.list_allowed_extensions()
    assert isinstance(listed, Ok)
    assert listed.value.includes(extension)


def test_allowing_twice_changes_nothing_the_second_time(
    allowlist: ProposedApiAllowlist,
) -> None:
    extension = ExtensionId.fake()

    first = allowlist.allow_proposed_api(extension)
    second = allowlist.allow_proposed_api(extension)

    assert first == Ok(AllowlistUpdate.ADDED)
    assert second == Ok(AllowlistUpdate.ALREADY_ALLOWED)


def test_allowing_keeps_other_extensions(allowlist: ProposedApiAllowlist) -> None:
    other = ExtensionId("someone.else")
    extension = ExtensionId.fake()

    _ = allowlist.allow_proposed_api(other)
    _ = allowlist.allow_proposed_api(extension)

    listed = allowlist.list_allowed_extensions()
    assert isinstance(listed, Ok)
    assert listed.value.includes(other)
    assert listed.value.includes(extension)


def test_ids_differing_only_in_case_are_the_same_extension(
    allowlist: ProposedApiAllowlist,
) -> None:
    extension = ExtensionId("Publisher.Name")

    _ = allowlist.allow_proposed_api(extension)
    again = allowlist.allow_proposed_api(extension.normalised())

    assert again == Ok(AllowlistUpdate.ALREADY_ALLOWED)
