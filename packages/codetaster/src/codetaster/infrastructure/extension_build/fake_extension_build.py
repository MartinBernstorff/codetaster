from typing import override

from safe_result import Err, Ok, Result

from codetaster.domain.domain_model.checkout import CheckoutPath
from codetaster.domain.domain_model.tool_errors import ToolError
from codetaster.domain.domain_model.vscode_extension import (
    BuiltExtension,
    ExtensionPackageError,
)
from codetaster.domain.secondary_ports.extension_build import ExtensionBuild


class FakeExtensionBuild(ExtensionBuild):
    """Returns `built` for every checkout, and keeps the checkouts it built in `built_in`."""

    def __init__(
        self,
        built: BuiltExtension,
        failure: ToolError | ExtensionPackageError | None = None,
    ) -> None:
        self.built = built
        self.failure = failure
        self.built_in: set[CheckoutPath] = set()

    @override
    def build_extension_package(
        self, checkout: CheckoutPath
    ) -> Result[BuiltExtension, ToolError | ExtensionPackageError]:
        if self.failure is not None:
            return Err(self.failure)
        self.built_in.add(checkout)
        return Ok(self.built)
