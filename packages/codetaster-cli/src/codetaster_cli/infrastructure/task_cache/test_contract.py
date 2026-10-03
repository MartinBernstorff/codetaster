"""Contract for TaskCache, run against every implementation."""

from pathlib import Path

import pytest
from safe_result import Ok

from codetaster_cli.domain.domain_model.checkout import CheckoutPath
from codetaster_cli.domain.secondary_ports.task_cache import TaskCache
from codetaster_cli.infrastructure.fakes.call_log import CallLog
from codetaster_cli.infrastructure.task_cache.fake_task_cache import FakeTaskCache
from codetaster_cli.infrastructure.task_cache.moon_task_cache import MoonTaskCache


@pytest.fixture(params=["moon", "fake"])
def cache(request: pytest.FixtureRequest) -> TaskCache:
    return MoonTaskCache() if request.param == "moon" else FakeTaskCache(CallLog.fake())


def test_clearing_a_missing_cache_succeeds(cache: TaskCache, tmp_path: Path) -> None:
    assert cache.clear_cache(CheckoutPath(tmp_path)) == Ok(None)


def test_clearing_an_existing_cache_succeeds(cache: TaskCache, tmp_path: Path) -> None:
    (tmp_path / ".moon" / "cache" / "states").mkdir(parents=True)

    assert cache.clear_cache(CheckoutPath(tmp_path)) == Ok(None)
