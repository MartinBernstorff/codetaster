"""Contract for ProposedApiAllowlist, run against every implementation."""

from pathlib import Path
from typing import Protocol, override

import pytest
from safe_result import Ok

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.vscode_extension import (
    AllowlistUpdate,
    ExtensionId,
    ExtensionIds,
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
from codetaster.infrastructure.proposed_api_allowlist.jsonc_document import (
    JsoncText,
    JsonKey,
    read_string_list,
)


class Allowlist(Protocol):
    """An allowlist that tests change through `port` and read back directly."""

    port: ProposedApiAllowlist

    def allowed_extensions(self) -> ExtensionIds: ...


class ArgvJsonFile(Allowlist):
    def __init__(self, location: Location) -> None:
        self.location = location
        self.port = ArgvJsonAllowlist(location)

    @override
    def allowed_extensions(self) -> ExtensionIds:
        text = JsoncText(self.location.root.read_text(encoding="utf-8-sig"))
        values = read_string_list(text, JsonKey("enable-proposed-api"))
        assert isinstance(values, Ok)
        return ExtensionIds(
            frozenset(ExtensionId(value.root) for value in values.value.root)
        )


class InMemoryAllowlist(Allowlist):
    def __init__(self, fake: InMemoryProposedApiAllowlist) -> None:
        self.fake = fake
        self.port = fake

    @override
    def allowed_extensions(self) -> ExtensionIds:
        return ExtensionIds(frozenset(self.fake.allowed))


@pytest.fixture(params=["argv.json", "in-memory"])
def allowlist(request: pytest.FixtureRequest, tmp_path: Path) -> Allowlist:
    if request.param == "argv.json":
        return ArgvJsonFile(Location(tmp_path / ".vscode" / "argv.json"))
    return InMemoryAllowlist(InMemoryProposedApiAllowlist())


def allows(allowlist: Allowlist, extension: ExtensionId) -> bool:
    return extension.normalised() in allowlist.allowed_extensions().normalised().root


def test_an_allowed_extension_is_listed(allowlist: Allowlist) -> None:
    extension = ExtensionId.fake()

    _ = allowlist.port.allow_proposed_api(extension)

    assert allows(allowlist, extension)


def test_allowing_twice_changes_nothing_the_second_time(allowlist: Allowlist) -> None:
    extension = ExtensionId.fake()

    first = allowlist.port.allow_proposed_api(extension)
    second = allowlist.port.allow_proposed_api(extension)

    assert first == Ok(AllowlistUpdate.ADDED)
    assert second == Ok(AllowlistUpdate.ALREADY_ALLOWED)


def test_allowing_keeps_other_extensions(allowlist: Allowlist) -> None:
    other = ExtensionId("someone.else")
    extension = ExtensionId.fake()

    _ = allowlist.port.allow_proposed_api(other)
    _ = allowlist.port.allow_proposed_api(extension)

    assert allows(allowlist, other)
    assert allows(allowlist, extension)


def test_ids_differing_only_in_case_are_the_same_extension(
    allowlist: Allowlist,
) -> None:
    extension = ExtensionId("Publisher.Name")

    _ = allowlist.port.allow_proposed_api(extension)
    again = allowlist.port.allow_proposed_api(extension.normalised())

    assert again == Ok(AllowlistUpdate.ALREADY_ALLOWED)
