import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.path_rules import PathPattern, PathRule
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import FileRating, RatingsFile
from codetaster.domain.domain_model.review.sampling import (
    Draw,
    Verdict,
    assess_file_change,
    draw_for_file_change,
)
from codetaster.domain.domain_model.review.test_strategies import (
    blob_shas,
    file_changes,
    probabilities,
    ratings_of,
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


def test_base_probability_one_always_samples() -> None:
    verdicts = {
        assess_file_change(change, Probability(1), None, None).verdict
        for change in changes_with_distinct_blobs()
    }

    assert verdicts == {Verdict.SAMPLED}


def test_base_probability_zero_never_samples() -> None:
    verdicts = {
        assess_file_change(change, Probability(0), None, None).verdict
        for change in changes_with_distinct_blobs()
    }

    assert verdicts == {Verdict.NO_REVIEW}


def test_a_draw_below_the_base_probability_is_sampled() -> None:
    change = FileChange.fake()
    draw = draw_for_file_change(change)
    above_draw = Probability(min(1, draw.root + 0.001))
    at_draw = Probability(draw.root)

    assert assess_file_change(change, above_draw, None, None).verdict is Verdict.SAMPLED
    assert assess_file_change(change, at_draw, None, None).verdict is Verdict.NO_REVIEW


def test_assessment_reports_its_inputs() -> None:
    change = FileChange.fake()
    base_probability = Probability(0.25)

    assessment = assess_file_change(change, base_probability, None, None)

    assert assessment.change == change
    assert assessment.base_probability == base_probability
    assert assessment.probability == base_probability


def test_draw_rejects_one() -> None:
    with pytest.raises(ValidationError):
        _ = Draw(1)


@given(change=file_changes(), base_probability=probabilities())
def test_an_unrated_file_never_needs_review(
    change: FileChange, base_probability: Probability
) -> None:
    assessment = assess_file_change(change, base_probability, None, None)

    assert assessment.verdict is not Verdict.NEEDS_REVIEW


def test_a_draw_below_the_rating_needs_review() -> None:
    change = FileChange.fake()
    draw = draw_for_file_change(change)
    rating = FileRating.fake().model_copy(
        update={"probability": Probability(min(1, draw.root + 0.001))}
    )

    assessment = assess_file_change(change, Probability(0), None, rating)

    assert assessment.verdict is Verdict.NEEDS_REVIEW
    assert assessment.rating == rating


def test_a_draw_at_the_rating_falls_back_to_sampling() -> None:
    change = FileChange.fake()
    draw = draw_for_file_change(change)
    rating = FileRating.fake().model_copy(
        update={"probability": Probability(draw.root)}
    )

    assessment = assess_file_change(change, Probability(1), None, rating)

    assert assessment.verdict is Verdict.SAMPLED


@given(change=file_changes(), base_probability=probabilities(), data=st.data())
def test_final_probability_is_at_least_base_and_rating(
    change: FileChange, base_probability: Probability, data: st.DataObject
) -> None:
    rating = data.draw(ratings_of(change))

    assessment = assess_file_change(change, base_probability, None, rating)

    assert assessment.probability.root >= base_probability.root
    assert assessment.probability.root >= rating.probability.root


@given(
    change=file_changes(),
    base_probability=probabilities(),
    raised=probabilities(),
    data=st.data(),
)
def test_raising_a_rating_never_lowers_the_group(
    change: FileChange,
    base_probability: Probability,
    raised: Probability,
    data: st.DataObject,
) -> None:
    rating = data.draw(ratings_of(change))
    higher = rating.model_copy(
        update={"probability": Probability(max(rating.probability.root, raised.root))}
    )

    before = assess_file_change(change, base_probability, None, rating).verdict
    after = assess_file_change(change, base_probability, None, higher).verdict

    # Verdict lists the most urgent group first.
    assert list(Verdict).index(after) <= list(Verdict).index(before)


@given(change=file_changes(), base_probability=probabilities(), data=st.data())
def test_a_rating_for_another_blob_is_the_same_as_no_rating(
    change: FileChange, base_probability: Probability, data: st.DataObject
) -> None:
    rating = data.draw(ratings_of(change))
    other_blob = data.draw(blob_shas().filter(lambda blob: blob != rating.blob))
    ratings = RatingsFile(ratings=(rating.model_copy(update={"blob": other_blob}),))

    rated = assess_file_change(
        change, base_probability, None, ratings.rating_for(change)
    )
    unrated = assess_file_change(change, base_probability, None, None)

    assert rated == unrated


def test_a_path_rule_replaces_the_base_probability() -> None:
    change = FileChange.fake()
    rule = PathRule(pattern=PathPattern("*"), probability=Probability(1))

    assessment = assess_file_change(change, Probability(0), rule, None)

    assert assessment.verdict is Verdict.SAMPLED
    assert assessment.base_probability == rule.probability
    assert assessment.path_rule == rule


def test_a_path_rule_of_zero_still_lets_a_rating_flag_the_file() -> None:
    change = FileChange.fake()
    rule = PathRule(pattern=PathPattern("*"), probability=Probability(0))
    rating = FileRating.fake().model_copy(update={"probability": Probability(1)})

    assessment = assess_file_change(change, Probability(1), rule, rating)

    assert assessment.verdict is Verdict.NEEDS_REVIEW
