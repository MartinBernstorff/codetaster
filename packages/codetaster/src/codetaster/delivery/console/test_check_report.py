from codetaster.delivery.console.check_report import check_report_from_result
from codetaster.domain.domain_model.review.changes import (
    FileChange,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.sampling import (
    FileAssessment,
    FileAssessments,
    Verdict,
)


def assessment_of(path: RepositoryPath, verdict: Verdict) -> FileAssessment:
    change = FileChange(
        before=None, after=FileVersion.fake().model_copy(update={"path": path})
    )
    return FileAssessment.fake().model_copy(
        update={"change": change, "verdict": verdict}
    )


def test_files_are_listed_by_verdict() -> None:
    needs_review = RepositoryPath("needs.py")
    no_review = RepositoryPath("skip.py")
    result = CheckResult.fake().model_copy(
        update={
            "assessments": FileAssessments(
                (
                    assessment_of(needs_review, Verdict.NEEDS_REVIEW),
                    assessment_of(no_review, Verdict.NO_REVIEW),
                )
            )
        }
    )

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert [file["path"] for file in report["needs-review"]] == [needs_review.root]
    assert [file["path"] for file in report["no-review"]] == [no_review.root]
    assert report["needs_review"] is True


def test_reports_each_files_decision_inputs() -> None:
    assessment = FileAssessment.fake()
    result = CheckResult.fake().model_copy(
        update={"assessments": FileAssessments((assessment,))}
    )
    expected = {
        "path": assessment.change.path().root,
        "previous_path": None,
        "change_type": assessment.change.change_type().value,
        "base_probability": assessment.base_probability.root,
        "probability": assessment.probability.root,
        "draw": assessment.draw.root,
    }

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    [file] = report["no-review"]
    assert file == expected
