from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.sampling import (
    FileAssessment,
    FileAssessments,
    Verdict,
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


def test_needs_review_when_any_file_does() -> None:
    result = result_with_verdicts(Verdict.NO_REVIEW, Verdict.NEEDS_REVIEW)

    assert result.verdict() is Verdict.NEEDS_REVIEW


def test_no_review_when_no_file_needs_it() -> None:
    result = result_with_verdicts(Verdict.NO_REVIEW)

    assert result.verdict() is Verdict.NO_REVIEW


def test_no_changed_files_need_no_review() -> None:
    result = result_with_verdicts()

    assert result.verdict() is Verdict.NO_REVIEW
