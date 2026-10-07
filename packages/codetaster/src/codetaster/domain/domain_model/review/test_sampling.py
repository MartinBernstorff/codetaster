import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileChanges,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    RatingsFile,
    RatingTarget,
)
from codetaster.domain.domain_model.review.sampling import (
    Draw,
    FileAssessment,
    Verdict,
    assess_file_changes,
    draw_for_file_change,
)
from codetaster.domain.domain_model.review.test_strategies import (
    blob_shas,
    distinct_file_changes,
    probabilities,
    ratings_of,
    top_rated_percentages,
)
from codetaster.domain.domain_model.review.top_rated import TopRatedPercentage


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


def rating_of(change: FileChange, probability: Probability) -> FileRating:
    target = RatingTarget.of_change(change)
    return FileRating.fake().model_copy(
        update={"path": target.path, "blob": target.blob, "probability": probability}
    )


def assessments_of(
    changes: list[FileChange],
    base_probability: Probability | None = None,
    ratings: RatingsFile | None = None,
    top_rated: TopRatedPercentage | None = None,
) -> tuple[FileAssessment, ...]:
    """Without ratings, at a base probability and top-rated percentage of 0."""
    return assess_file_changes(
        FileChanges(tuple(changes)),
        base_probability or Probability(0),
        ratings or RatingsFile(ratings=()),
        top_rated or TopRatedPercentage(0),
    ).root


def stale_ratings_of(change: FileChange) -> st.SearchStrategy[FileRating]:
    """Ratings for `change`'s path, but for another version of the file."""
    return ratings_of(change).flatmap(
        lambda rating: (
            blob_shas()
            .filter(lambda blob: blob != rating.blob)
            .map(lambda blob: rating.model_copy(update={"blob": blob}))
        )
    )


def needs_review(assessments: tuple[FileAssessment, ...]) -> list[FileChange]:
    return [
        assessment.change
        for assessment in assessments
        if assessment.verdict is Verdict.NEEDS_REVIEW
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
    assessments = assessments_of(
        changes_with_distinct_blobs(), base_probability=Probability(1)
    )

    assert {assessment.verdict for assessment in assessments} == {Verdict.SAMPLED}


def test_base_probability_zero_never_samples() -> None:
    assessments = assessments_of(
        changes_with_distinct_blobs(), base_probability=Probability(0)
    )

    assert {assessment.verdict for assessment in assessments} == {Verdict.NO_REVIEW}


def test_a_draw_below_the_base_probability_is_sampled() -> None:
    change = FileChange.fake()
    draw = draw_for_file_change(change)
    above_draw = Probability(min(1, draw.root + 0.001))
    at_draw = Probability(draw.root)

    [sampled] = assessments_of([change], base_probability=above_draw)
    [not_sampled] = assessments_of([change], base_probability=at_draw)

    assert sampled.verdict is Verdict.SAMPLED
    assert not_sampled.verdict is Verdict.NO_REVIEW


def test_assessment_reports_its_inputs() -> None:
    change = FileChange.fake()
    base_probability = Probability(0.25)
    rating = rating_of(change, Probability(0.5))

    [assessment] = assessments_of(
        [change], base_probability, RatingsFile(ratings=(rating,))
    )

    assert assessment.change == change
    assert assessment.base_probability == base_probability
    assert assessment.rating == rating
    assert assessment.draw == draw_for_file_change(change)


def test_draw_rejects_one() -> None:
    with pytest.raises(ValidationError):
        _ = Draw(1)


def test_top_rated_percentage_above_100_is_invalid() -> None:
    with pytest.raises(ValidationError):
        _ = TopRatedPercentage(101)


def test_the_highest_rated_files_need_review() -> None:
    changes = changes_with_distinct_blobs()[:10]
    ratings = RatingsFile(
        ratings=tuple(
            rating_of(change, Probability(index / 10))
            for index, change in enumerate(changes)
        )
    )

    assessments = assessments_of(
        changes, ratings=ratings, top_rated=TopRatedPercentage(20)
    )

    assert needs_review(assessments) == changes[-2:]


def test_the_number_of_top_rated_files_is_rounded_up() -> None:
    changes = changes_with_distinct_blobs()[:3]
    ratings = RatingsFile(
        ratings=tuple(rating_of(change, Probability(0.5)) for change in changes)
    )

    assessments = assessments_of(
        changes, ratings=ratings, top_rated=TopRatedPercentage(1)
    )

    assert len(needs_review(assessments)) == 1


def test_a_top_rated_percentage_of_zero_picks_no_file() -> None:
    changes = changes_with_distinct_blobs()[:3]
    ratings = RatingsFile(
        ratings=tuple(rating_of(change, Probability(1)) for change in changes)
    )

    assessments = assessments_of(
        changes, ratings=ratings, top_rated=TopRatedPercentage(0)
    )

    assert needs_review(assessments) == []


def test_equal_ratings_pick_the_lower_draw() -> None:
    changes = changes_with_distinct_blobs()[:2]
    ratings = RatingsFile(
        ratings=tuple(rating_of(change, Probability(0.5)) for change in changes)
    )
    lower_draw = min(changes, key=lambda change: draw_for_file_change(change).root)

    assessments = assessments_of(
        changes, ratings=ratings, top_rated=TopRatedPercentage(50)
    )

    assert needs_review(assessments) == [lower_draw]


@given(
    changes=distinct_file_changes(),
    base_probability=probabilities(),
    top_rated=top_rated_percentages(),
)
def test_an_unrated_file_never_needs_review(
    changes: list[FileChange],
    base_probability: Probability,
    top_rated: TopRatedPercentage,
) -> None:
    assessments = assessments_of(changes, base_probability, top_rated=top_rated)

    assert needs_review(assessments) == []


@given(
    changes=distinct_file_changes().filter(lambda changes: len(changes) > 0),
    base_probability=probabilities(),
    top_rated=top_rated_percentages(),
    data=st.data(),
)
def test_raising_a_rating_never_lowers_the_group(
    changes: list[FileChange],
    base_probability: Probability,
    top_rated: TopRatedPercentage,
    data: st.DataObject,
) -> None:
    ratings = [data.draw(ratings_of(change)) for change in changes]
    raised = data.draw(probabilities())
    first = ratings[0]
    higher = first.model_copy(
        update={"probability": Probability(max(first.probability.root, raised.root))}
    )

    [before, *_] = assessments_of(
        changes, base_probability, RatingsFile(ratings=tuple(ratings)), top_rated
    )
    [after, *_] = assessments_of(
        changes,
        base_probability,
        RatingsFile(ratings=(higher, *ratings[1:])),
        top_rated,
    )

    # Verdict lists the most urgent group first.
    order = list(Verdict)
    assert order.index(after.verdict) <= order.index(before.verdict)


@given(
    changes=distinct_file_changes(),
    base_probability=probabilities(),
    top_rated=top_rated_percentages(),
    data=st.data(),
)
def test_a_rating_for_another_blob_is_the_same_as_no_rating(
    changes: list[FileChange],
    base_probability: Probability,
    top_rated: TopRatedPercentage,
    data: st.DataObject,
) -> None:
    stale = [data.draw(stale_ratings_of(change)) for change in changes]

    rated = assessments_of(
        changes, base_probability, RatingsFile(ratings=tuple(stale)), top_rated
    )
    unrated = assessments_of(changes, base_probability, top_rated=top_rated)

    assert rated == unrated
