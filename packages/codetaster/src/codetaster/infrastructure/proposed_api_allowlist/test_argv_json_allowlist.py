from pathlib import Path

from safe_result import Err, Ok

from codetaster.domain.domain_model.filesystem import Location
from codetaster.domain.domain_model.vscode_extension import (
    AllowlistUpdate,
    ExtensionId,
)
from codetaster.infrastructure.proposed_api_allowlist.argv_json_allowlist import (
    ArgvJsonAllowlist,
)

# Abridged from the file VS Code writes on first start.
VSCODE_DEFAULT_ARGV = """\
// This configuration file allows you to pass permanent command line arguments to VS Code.
//
// NOTE: Changing this file requires a restart of VS Code.
{
\t// Use software rendering instead of hardware accelerated rendering.
\t// "disable-hardware-acceleration": true,

\t// Unique id used for correlating crash reports sent from this instance.
\t// Do not edit this value.
\t"crash-reporter-id": "00000000-0000-0000-0000-000000000000",
}
"""


def test_adds_to_vscodes_default_file_and_keeps_its_settings(tmp_path: Path) -> None:
    location = tmp_path / "argv.json"
    _ = location.write_text(VSCODE_DEFAULT_ARGV)
    extension = ExtensionId.fake()
    allowlist = ArgvJsonAllowlist(Location(location))

    result = allowlist.allow_proposed_api(extension)

    assert result == Ok(AllowlistUpdate.ADDED)
    updated = location.read_text()
    for line in VSCODE_DEFAULT_ARGV.splitlines():
        assert line in updated
    listed = allowlist.list_allowed_extensions()
    assert isinstance(listed, Ok)
    assert listed.value.includes(extension)


def test_an_unexpected_value_is_an_error_and_the_file_is_left_alone(
    tmp_path: Path,
) -> None:
    location = tmp_path / "argv.json"
    content = '{"enable-proposed-api": "not a list"}'
    _ = location.write_text(content)

    result = ArgvJsonAllowlist(Location(location)).allow_proposed_api(
        ExtensionId.fake()
    )

    assert isinstance(result, Err)
    assert location.read_text() == content


def test_reads_a_file_starting_with_a_byte_order_mark(tmp_path: Path) -> None:
    location = tmp_path / "argv.json"
    _ = location.write_text("{}", encoding="utf-8-sig")
    extension = ExtensionId.fake()

    result = ArgvJsonAllowlist(Location(location)).allow_proposed_api(extension)

    assert result == Ok(AllowlistUpdate.ADDED)
