from codetaster_cli.domain.domain_model.worktrees import WorktreeCount


def test_only_a_single_checkout_is_the_last_one() -> None:
    assert WorktreeCount(1).is_last_checkout()
    assert not WorktreeCount(2).is_last_checkout()
    assert WorktreeCount(3).others() == WorktreeCount(2)
