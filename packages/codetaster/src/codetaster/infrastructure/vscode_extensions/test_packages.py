"""Builds minimal `.vsix` packages for tests. Holds no tests itself."""

import json
import zipfile

from codetaster.domain.domain_model.vscode_extension import (
    ExtensionId,
    ExtensionPackagePath,
)


def write_minimal_vsix(
    package: ExtensionPackagePath, extension: ExtensionId
) -> ExtensionPackagePath:
    """Write a package for `extension` that `code --install-extension` accepts."""
    publisher, name = extension.root.split(".", maxsplit=1)
    manifest = {
        "name": name,
        "publisher": publisher,
        "version": "0.0.1",
        "engines": {"vscode": "^1.0.0"},
    }
    package.root.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package.root, "w") as archive:
        archive.writestr("extension/package.json", json.dumps(manifest))
    return package
