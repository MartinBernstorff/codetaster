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
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.test_strategies import probabilities


def sampling_at(
    base_probability: Probability,
    commented: CommentedFileCount | None = None,
    viewed: ViewedFileCount | None = None,
    weight: BaseProbabilityWeight | None = None,
) -> AdaptiveSampling:
    """Without evidence, at a weight of 10."""
    return AdaptiveSampling(
        base_probability=base_probability,
        weight=weight or BaseProbabilityWeight(10),
        evidence=SamplingEvidence(
            commented_files=commented or CommentedFileCount(0),
            viewed_files=viewed or ViewedFileCount(0),
        ),
    )


def commented_counts() -> st.SearchStrategy[CommentedFileCount]:
    return st.builds(CommentedFileCount, st.integers(min_value=0, max_value=50))


def viewed_counts() -> st.SearchStrategy[ViewedFileCount]:
    return st.builds(ViewedFileCount, st.integers(min_value=0, max_value=50))


@pytest.mark.parametrize(
    ("commented", "viewed", "expected"),
    [
        (CommentedFileCount(1), ViewedFileCount(0), Probability(2 / 11)),
        (CommentedFileCount(2), ViewedFileCount(0), Probability(0.25)),
        (CommentedFileCount(1), ViewedFileCount(5), Probability(0.125)),
    ],
)
def test_effective_probability_is_the_posterior_mean(
    commented: CommentedFileCount, viewed: ViewedFileCount, expected: Probability
) -> None:
    sampling = sampling_at(Probability(0.1), commented, viewed)

    assert sampling.effective_probability().root == pytest.approx(expected.root)


def test_viewed_files_never_lower_the_effective_probability_below_base() -> None:
    base = Probability(0.1)

    sampling = sampling_at(base, viewed=ViewedFileCount(20))

    assert sampling.effective_probability() == base


def test_without_evidence_every_probability_is_unchanged() -> None:
    probability = Probability(0.37)

    sampling = sampling_at(Probability(0.1))

    assert sampling.adjusted(probability) == probability


def test_the_base_probability_is_adjusted_to_the_effective_probability() -> None:
    base = Probability(0.1)
    sampling = sampling_at(base, commented=CommentedFileCount(1))

    assert sampling.adjusted(base).root == pytest.approx(
        sampling.effective_probability().root
    )


def test_a_path_rule_probability_is_adjusted_by_the_same_odds_ratio() -> None:
    # Base 0.1 -> 0.25 multiplies the odds by 3, so 0.5 (odds 1) becomes 0.75.
    sampling = sampling_at(Probability(0.1), commented=CommentedFileCount(2))

    assert sampling.adjusted(Probability(0.5)).root == pytest.approx(0.75)


@pytest.mark.parametrize("unchanged", [Probability(0), Probability(1)])
def test_zero_and_one_are_never_adjusted(unchanged: Probability) -> None:
    sampling = sampling_at(Probability(0.1), commented=CommentedFileCount(3))

    assert sampling.adjusted(unchanged) == unchanged


@pytest.mark.parametrize("base", [Probability(0), Probability(1)])
def test_a_base_probability_of_zero_or_one_adjusts_nothing(base: Probability) -> None:
    probability = Probability(0.3)
    sampling = sampling_at(base, commented=CommentedFileCount(3))

    assert sampling.adjusted(probability) == probability


def test_a_lower_weight_lets_each_comment_count_more() -> None:
    one = CommentedFileCount(1)
    light = sampling_at(Probability(0.1), one, weight=BaseProbabilityWeight(2))
    heavy = sampling_at(Probability(0.1), one, weight=BaseProbabilityWeight(10))

    assert light.effective_probability().root > heavy.effective_probability().root


@given(
    base=probabilities(),
    probability=probabilities(),
    commented=commented_counts(),
    viewed=viewed_counts(),
)
def test_adjusting_never_lowers_a_probability(
    base: Probability,
    probability: Probability,
    commented: CommentedFileCount,
    viewed: ViewedFileCount,
) -> None:
    sampling = sampling_at(base, commented, viewed)

    assert sampling.adjusted(probability).root >= probability.root


@given(
    base=probabilities(),
    probability=probabilities(),
    commented=commented_counts(),
    viewed=viewed_counts(),
)
def test_another_commented_file_never_lowers_a_probability(
    base: Probability,
    probability: Probability,
    commented: CommentedFileCount,
    viewed: ViewedFileCount,
) -> None:
    fewer = sampling_at(base, commented, viewed)
    more = sampling_at(base, CommentedFileCount(commented.root + 1), viewed)

    assert more.adjusted(probability).root >= fewer.adjusted(probability).root


def test_a_negative_count_is_invalid() -> None:
    with pytest.raises(ValidationError):
        _ = CommentedFileCount(-1)


def test_a_weight_of_zero_is_invalid() -> None:
    with pytest.raises(ValidationError):
        _ = BaseProbabilityWeight(0)
