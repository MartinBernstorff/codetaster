import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from codetaster.domain.domain_model.review.adaptive_sampling import (
    AdaptiveSampling,
    BaseProbabilityWeight,
    CommentedFileCount,
    SamplingEvidence,
    ViewedFileCount,
)
from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileChanges,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.needs_review_threshold import (
    NeedsReviewThreshold,
)
from codetaster.domain.domain_model.review.path_rules import (
    PathPattern,
    PathRule,
    PathRules,
)
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    FileRatings,
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
    needs_review_thresholds,
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


def rating_of(change: FileChange, probability: Probability) -> FileRating:
    target = RatingTarget.of_change(change)
    return FileRating.fake().model_copy(
        update={"path": target.path, "blob": target.blob, "probability": probability}
    )


def assessments_of(
    changes: list[FileChange],
    base_probability: Probability | None = None,
    ratings: FileRatings | None = None,
    threshold: NeedsReviewThreshold | None = None,
    path_rules: PathRules | None = None,
) -> tuple[FileAssessment, ...]:
    """Without ratings, path rules or evidence, at a base probability of 0 and a
    needs-review threshold of 1."""
    return assess_file_changes(
        FileChanges(tuple(changes)),
        sampling_with(base_probability or Probability(0), SamplingEvidence.none()),
        path_rules or PathRules(()),
        ratings or FileRatings(()),
        threshold or NeedsReviewThreshold(1),
    ).root


def sampling_with(
    base_probability: Probability, evidence: SamplingEvidence
) -> AdaptiveSampling:
    return AdaptiveSampling(
        base_probability=base_probability,
        weight=BaseProbabilityWeight(10),
        evidence=evidence,
    )


def assessments_with_evidence(
    changes: list[FileChange], base_probability: Probability, evidence: SamplingEvidence
) -> tuple[FileAssessment, ...]:
    """Without ratings or path rules, at a needs-review threshold of 1."""
    return assess_file_changes(
        FileChanges(tuple(changes)),
        sampling_with(base_probability, evidence),
        PathRules(()),
        FileRatings(()),
        NeedsReviewThreshold(1),
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

    [assessment] = assessments_of([change], base_probability, FileRatings((rating,)))

    assert assessment.change == change
    assert assessment.base_probability == base_probability
    assert assessment.rating == rating
    assert assessment.draw == draw_for_file_change(change)


def test_draw_rejects_one() -> None:
    with pytest.raises(ValidationError):
        _ = Draw(1)


def test_needs_review_threshold_above_one_is_invalid() -> None:
    with pytest.raises(ValidationError):
        _ = NeedsReviewThreshold(1.1)


def test_files_rated_at_or_above_the_threshold_need_review() -> None:
    changes = changes_with_distinct_blobs()[:10]
    ratings = FileRatings(
        tuple(
            rating_of(change, Probability(index / 10))
            for index, change in enumerate(changes)
        )
    )

    assessments = assessments_of(
        changes, ratings=ratings, threshold=NeedsReviewThreshold(0.7)
    )

    assert needs_review(assessments) == changes[7:]


def test_a_file_below_the_threshold_can_still_be_sampled() -> None:
    change = FileChange.fake()

    [assessment] = assessments_of(
        [change],
        base_probability=Probability(1),
        ratings=FileRatings((rating_of(change, Probability(0.4)),)),
        threshold=NeedsReviewThreshold(0.5),
    )

    assert assessment.verdict is Verdict.SAMPLED


@given(
    changes=distinct_file_changes(),
    base_probability=probabilities(),
    threshold=needs_review_thresholds(),
)
def test_an_unrated_file_never_needs_review(
    changes: list[FileChange],
    base_probability: Probability,
    threshold: NeedsReviewThreshold,
) -> None:
    assessments = assessments_of(changes, base_probability, threshold=threshold)

    assert needs_review(assessments) == []


@given(
    changes=distinct_file_changes().filter(lambda changes: len(changes) > 0),
    base_probability=probabilities(),
    threshold=needs_review_thresholds(),
    data=st.data(),
)
def test_raising_a_rating_never_lowers_the_group(
    changes: list[FileChange],
    base_probability: Probability,
    threshold: NeedsReviewThreshold,
    data: st.DataObject,
) -> None:
    ratings = [data.draw(ratings_of(change)) for change in changes]
    raised = data.draw(probabilities())
    first = ratings[0]
    higher = first.model_copy(
        update={"probability": Probability(max(first.probability.root, raised.root))}
    )

    [before, *_] = assessments_of(
        changes,
        base_probability,
        FileRatings(tuple(ratings)),
        threshold,
    )
    [after, *_] = assessments_of(
        changes,
        base_probability,
        FileRatings((higher, *ratings[1:])),
        threshold,
    )

    # Verdict lists the most urgent group first.
    order = list(Verdict)
    assert order.index(after.verdict) <= order.index(before.verdict)


@given(
    changes=distinct_file_changes(),
    base_probability=probabilities(),
    threshold=needs_review_thresholds(),
    data=st.data(),
)
def test_a_rating_for_another_blob_is_the_same_as_no_rating(
    changes: list[FileChange],
    base_probability: Probability,
    threshold: NeedsReviewThreshold,
    data: st.DataObject,
) -> None:
    stale = [data.draw(stale_ratings_of(change)) for change in changes]

    rated = assessments_of(
        changes, base_probability, FileRatings(tuple(stale)), threshold
    )
    unrated = assessments_of(changes, base_probability, threshold=threshold)

    assert rated == unrated


def test_a_path_rule_replaces_the_base_probability() -> None:
    change = FileChange.fake()
    rule = PathRule(pattern=PathPattern("*"), probability=Probability(1))

    [assessment] = assessments_of(
        [change], base_probability=Probability(0), path_rules=PathRules((rule,))
    )

    assert assessment.verdict is Verdict.SAMPLED
    assert assessment.base_probability == rule.probability
    assert assessment.path_rule == rule


def test_a_path_rule_of_zero_still_lets_a_file_above_the_threshold_need_review() -> (
    None
):
    change = FileChange.fake()
    rule = PathRule(pattern=PathPattern("*"), probability=Probability(0))

    [assessment] = assessments_of(
        [change],
        base_probability=Probability(1),
        ratings=FileRatings((rating_of(change, Probability(1)),)),
        threshold=NeedsReviewThreshold(1),
        path_rules=PathRules((rule,)),
    )

    assert assessment.verdict is Verdict.NEEDS_REVIEW


def test_a_commented_file_raises_the_sampling_probability() -> None:
    change = FileChange.fake()
    base_probability = Probability(0.1)
    commented = SamplingEvidence(
        commented_files=CommentedFileCount(2), viewed_files=ViewedFileCount(0)
    )
    raised = Probability(0.25)

    [assessment] = assessments_with_evidence([change], base_probability, commented)

    assert assessment.base_probability == base_probability
    assert assessment.sampling_probability.root == pytest.approx(raised.root)


def test_without_evidence_the_sampling_probability_is_the_base_probability() -> None:
    base_probability = Probability(0.1)

    [assessment] = assessments_of([FileChange.fake()], base_probability)

    assert assessment.sampling_probability == base_probability


@given(
    changes=distinct_file_changes(),
    base_probability=probabilities(),
    commented=st.builds(CommentedFileCount, st.integers(min_value=0, max_value=20)),
)
def test_evidence_only_adds_sampled_files(
    changes: list[FileChange],
    base_probability: Probability,
    commented: CommentedFileCount,
) -> None:
    evidence = SamplingEvidence(
        commented_files=commented, viewed_files=ViewedFileCount(0)
    )

    without = assessments_of(changes, base_probability)
    with_evidence = assessments_with_evidence(changes, base_probability, evidence)

    assert {
        assessment.change.path()
        for assessment in without
        if assessment.verdict is Verdict.SAMPLED
    } <= {
        assessment.change.path()
        for assessment in with_evidence
        if assessment.verdict is Verdict.SAMPLED
    }
