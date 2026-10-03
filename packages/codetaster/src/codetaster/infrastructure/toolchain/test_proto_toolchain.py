from pathlib import Path

import pytest
from safe_result import Err

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolNotFoundError
from codetaster.infrastructure.toolchain.proto_toolchain import ProtoToolchain


def test_missing_proto_explains_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proto_install_instructions = "https://moonrepo.dev/docs/proto/install"
    monkeypatch.setenv("PATH", str(tmp_path))

    result = ProtoToolchain().install_pinned_tools(CheckoutPath(tmp_path))

    assert isinstance(result, Err)
    assert isinstance(result.error, ToolNotFoundError)
    assert proto_install_instructions in str(result.error)
