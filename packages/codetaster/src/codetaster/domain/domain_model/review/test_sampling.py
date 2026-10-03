import pytest
from pydantic import ValidationError

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.sampling import (
    Draw,
    Probability,
    Verdict,
    assess_file_change,
    draw_for_file_change,
)


def changes_with_distinct_blobs() -> list[FileChange]:
    return [
        FileChange(
            before=None,
            after=FileVersion(
                path=RepositoryPath.fake(), blob=BlobSha(f"{index:040x}")
            ),
        )
        for index in range(1000)
    ]


def test_probability_below_zero_is_invalid() -> None:
    with pytest.raises(ValidationError):
        _ = Probability(-0.1)


def test_probability_above_one_is_invalid() -> None:
    with pytest.raises(ValidationError):
        _ = Probability(1.1)


def test_draw_is_reproducible() -> None:
    change = FileChange.fake()

    assert draw_for_file_change(change) == draw_for_file_change(change.model_copy())


def test_draw_changes_when_the_blob_changes() -> None:
    change = FileChange.fake()
    assert change.after is not None
    edited = change.model_copy(
        update={"after": change.after.model_copy(update={"blob": BlobSha("c" * 40)})}
    )

    assert draw_for_file_change(edited) != draw_for_file_change(change)


def test_draw_changes_when_the_path_changes() -> None:
    change = FileChange.fake()
    assert change.after is not None
    moved = change.model_copy(
        update={
            "after": change.after.model_copy(
                update={"path": RepositoryPath("elsewhere.py")}
            )
        }
    )

    assert draw_for_file_change(moved) != draw_for_file_change(change)


def test_draws_fall_in_zero_to_one() -> None:
    draws = [
        draw_for_file_change(change).root for change in changes_with_distinct_blobs()
    ]

    assert all(0 <= draw < 1 for draw in draws)
    # Spread over the interval, not clustered in one part of it.
    assert min(draws) < 0.01
    assert max(draws) > 0.99


def test_probability_one_always_needs_review() -> None:
    verdicts = {
        assess_file_change(change, Probability(1)).verdict
        for change in changes_with_distinct_blobs()
    }

    assert verdicts == {Verdict.NEEDS_REVIEW}


def test_probability_zero_never_needs_review() -> None:
    verdicts = {
        assess_file_change(change, Probability(0)).verdict
        for change in changes_with_distinct_blobs()
    }

    assert verdicts == {Verdict.NO_REVIEW}


def test_a_draw_below_the_probability_needs_review() -> None:
    change = FileChange.fake()
    draw = draw_for_file_change(change)
    above_draw = Probability(min(1, draw.root + 0.001))
    at_draw = Probability(draw.root)

    assert assess_file_change(change, above_draw).verdict is Verdict.NEEDS_REVIEW
    assert assess_file_change(change, at_draw).verdict is Verdict.NO_REVIEW


def test_assessment_reports_its_inputs() -> None:
    change = FileChange.fake()
    base_probability = Probability(0.25)

    assessment = assess_file_change(change, base_probability)

    assert assessment.change == change
    assert assessment.base_probability == base_probability
    assert assessment.probability == base_probability


def test_draw_rejects_one() -> None:
    with pytest.raises(ValidationError):
        _ = Draw(1)
