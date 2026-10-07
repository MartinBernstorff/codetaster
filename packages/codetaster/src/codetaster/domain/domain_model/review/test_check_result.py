from collections import Counter

from hypothesis import given
from hypothesis import strategies as st

from codetaster.domain.domain_model.review.changes import FileChange, FileChanges
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.path_rules import PathRules
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.ratings import RatingsFile
from codetaster.domain.domain_model.review.sampling import (
    FileAssessment,
    FileAssessments,
    Verdict,
    assess_file_changes,
)
from codetaster.domain.domain_model.review.test_strategies import (
    distinct_file_changes,
    probabilities,
    ratings_of,
    top_rated_percentages,
)
from codetaster.domain.domain_model.review.top_rated import TopRatedPercentage


def result_with_verdicts(*verdicts: Verdict) -> CheckResult:
    return CheckResult.fake().model_copy(
        update={
            "assessments": FileAssessments(
                tuple(
                    FileAssessment.fake().model_copy(update={"verdict": verdict})
                    for verdict in verdicts
                )
            )
        }
    )


def test_needs_review_when_any_file_needs_review() -> None:
    result = result_with_verdicts(Verdict.NO_REVIEW, Verdict.NEEDS_REVIEW)

    assert result.verdict() is Verdict.NEEDS_REVIEW


def test_needs_review_wins_over_sampled() -> None:
    result = result_with_verdicts(Verdict.SAMPLED, Verdict.NEEDS_REVIEW)

    assert result.verdict() is Verdict.NEEDS_REVIEW


def test_sampled_when_a_file_is_sampled_and_none_needs_review() -> None:
    result = result_with_verdicts(Verdict.NO_REVIEW, Verdict.SAMPLED)

    assert result.verdict() is Verdict.SAMPLED


def test_no_review_when_no_file_needs_it() -> None:
    result = result_with_verdicts(Verdict.NO_REVIEW)

    assert result.verdict() is Verdict.NO_REVIEW


def test_no_changed_files_need_no_review() -> None:
    result = result_with_verdicts()

    assert result.verdict() is Verdict.NO_REVIEW


@given(
    changes=distinct_file_changes(),
    base_probability=probabilities(),
    top_rated=top_rated_percentages(),
    data=st.data(),
)
def test_the_groups_partition_the_changed_files(
    changes: list[FileChange],
    base_probability: Probability,
    top_rated: TopRatedPercentage,
    data: st.DataObject,
) -> None:
    ratings = RatingsFile(
        ratings=tuple(
            rating
            for change in changes
            if (rating := data.draw(st.one_of(st.none(), ratings_of(change))))
            is not None
        )
    )
    result = CheckResult.fake().model_copy(
        update={
            "assessments": assess_file_changes(
                FileChanges(tuple(changes)),
                base_probability,
                PathRules(()),
                ratings,
                top_rated,
            )
        }
    )

    grouped = [
        assessment.change
        for verdict in Verdict
        for assessment in result.assessments_with(verdict).root
    ]

    assert Counter(grouped) == Counter(changes)
