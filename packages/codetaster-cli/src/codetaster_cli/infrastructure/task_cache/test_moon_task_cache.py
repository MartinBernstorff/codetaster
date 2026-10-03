from pathlib import Path

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.infrastructure.task_cache.moon_task_cache import MoonTaskCache


def test_clearing_deletes_only_the_cache(tmp_path: Path) -> None:
    (tmp_path / ".moon" / "cache").mkdir(parents=True)
    _ = (tmp_path / ".moon" / "workspace.yml").write_text("")

    _ = MoonTaskCache().clear_cache(CheckoutPath(tmp_path))

    assert not (tmp_path / ".moon" / "cache").exists()
    assert (tmp_path / ".moon" / "workspace.yml").exists()
