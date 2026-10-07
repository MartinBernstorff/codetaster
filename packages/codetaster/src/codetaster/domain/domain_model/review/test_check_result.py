from collections import Counter

from hypothesis import given
from hypothesis import strategies as st

from codetaster.domain.domain_model.review.changes import FileChange
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.probability import Probability
from codetaster.domain.domain_model.review.sampling import (
    FileAssessment,
    FileAssessments,
    Verdict,
    assess_file_change,
)
from codetaster.domain.domain_model.review.test_strategies import (
    file_changes,
    probabilities,
    ratings_of,
)


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
    changes=st.lists(file_changes(), max_size=20),
    base_probability=probabilities(),
    data=st.data(),
)
def test_the_groups_partition_the_changed_files(
    changes: list[FileChange], base_probability: Probability, data: st.DataObject
) -> None:
    result = CheckResult.fake().model_copy(
        update={
            "assessments": FileAssessments(
                tuple(
                    assess_file_change(
                        change,
                        base_probability,
                        data.draw(st.one_of(st.none(), ratings_of(change))),
                    )
                    for change in changes
                )
            )
        }
    )

    grouped = [
        assessment.change
        for verdict in Verdict
        for assessment in result.assessments_with(verdict).root
    ]

    assert Counter(grouped) == Counter(changes)
