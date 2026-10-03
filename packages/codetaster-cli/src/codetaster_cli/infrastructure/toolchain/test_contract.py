"""Contract for Toolchain, run against every implementation."""

from pathlib import Path

import pytest
from safe_result import Ok

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.secondary_ports.toolchain import Toolchain
from codetaster_cli.infrastructure.fakes.call_log import CallLog
from codetaster_cli.infrastructure.toolchain.fake_toolchain import FakeToolchain
from codetaster_cli.infrastructure.toolchain.proto_toolchain import ProtoToolchain


@pytest.fixture(params=["proto", "fake"])
def toolchain(request: pytest.FixtureRequest) -> Toolchain:
    return (
        ProtoToolchain() if request.param == "proto" else FakeToolchain(CallLog.fake())
    )


def test_installing_with_nothing_pinned_succeeds(
    toolchain: Toolchain, tmp_path: Path
) -> None:
    _ = (tmp_path / ".prototools").write_text("")

    assert toolchain.install_pinned_tools(CheckoutPath(tmp_path)) == Ok(None)
