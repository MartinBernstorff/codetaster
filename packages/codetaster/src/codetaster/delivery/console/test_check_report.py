from codetaster.delivery.console.check_report import check_report_from_result
from codetaster.domain.domain_model.review.adaptive_sampling import AdaptiveSampling
from codetaster.domain.domain_model.review.changes import (
    FileChange,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.needs_review_threshold import (
    NeedsReviewThreshold,
)
from codetaster.domain.domain_model.review.path_rules import PathRule
from codetaster.domain.domain_model.review.ratings import (
    FileRating,
    PullRequestOverview,
)
from codetaster.domain.domain_model.review.ratings_validation import (
    InvalidRatingsFile,
)
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


def result_with(*assessments: FileAssessment) -> CheckResult:
    return CheckResult.fake().model_copy(
        update={"assessments": FileAssessments(assessments)}
    )


def test_files_are_listed_by_verdict() -> None:
    needs_review = RepositoryPath("needs.py")
    sampled = RepositoryPath("sampled.py")
    no_review = RepositoryPath("skip.py")
    result = result_with(
        assessment_of(needs_review, Verdict.NEEDS_REVIEW),
        assessment_of(sampled, Verdict.SAMPLED),
        assessment_of(no_review, Verdict.NO_REVIEW),
    )

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert [file["path"] for file in report["needs-review"]] == [needs_review.root]
    assert [file["path"] for file in report["sampled"]] == [sampled.root]
    assert [file["path"] for file in report["no-review"]] == [no_review.root]


def test_a_sampled_file_means_the_change_needs_review() -> None:
    result = result_with(
        assessment_of(RepositoryPath("sampled.py"), Verdict.SAMPLED),
        assessment_of(RepositoryPath("skip.py"), Verdict.NO_REVIEW),
    )

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert report["needs_review"] is True


def test_only_no_review_files_means_the_change_needs_no_review() -> None:
    result = result_with(assessment_of(RepositoryPath.fake(), Verdict.NO_REVIEW))

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert report["needs_review"] is False


def test_reports_an_invalid_ratings_file() -> None:
    problem = InvalidRatingsFile.fake()
    result = CheckResult.fake().model_copy(update={"ratings_problem": problem})

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert str(problem.location.root) in report["ratings_error"]
    assert problem.reason.root in report["ratings_error"]


def test_a_valid_ratings_file_is_no_ratings_error() -> None:
    result = CheckResult.fake().model_copy(update={"ratings_problem": None})

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert report["ratings_error"] is None


def test_reports_the_overview() -> None:
    overview = PullRequestOverview.fake()
    result = CheckResult.fake().model_copy(update={"overview": overview})

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert report["overview"] == overview.model_dump(mode="json")


def test_no_ratings_file_is_no_overview() -> None:
    result = CheckResult.fake().model_copy(update={"overview": None})

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert report["overview"] is None


def test_schema_version_is_five() -> None:
    expected = 5

    report = check_report_from_result(CheckResult.fake()).model_dump(
        mode="json", by_alias=True
    )

    assert report["schema_version"] == expected


def test_reports_the_needs_review_threshold() -> None:
    threshold = NeedsReviewThreshold.fake()
    result = CheckResult.fake().model_copy(update={"needs_review_threshold": threshold})

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert report["needs_review_threshold"] == threshold.root


def test_reports_each_files_decision_inputs() -> None:
    assessment = FileAssessment.fake()
    result = result_with(assessment)
    expected = {
        "path": assessment.change.path().root,
        "previous_path": None,
        "change_type": assessment.change.change_type().value,
        "base_probability": assessment.base_probability.root,
        "sampling_probability": assessment.sampling_probability.root,
        "path_rule": None,
        "rating": None,
        "unrated": True,
        "draw": assessment.draw.root,
    }

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    [file] = report["no-review"]
    assert file == expected


def test_reports_a_rated_files_rating_and_category() -> None:
    rating = FileRating.fake()
    assessment = FileAssessment.fake().model_copy(update={"rating": rating})
    expected = {
        "probability": rating.probability.root,
        "category": rating.category.root,
    }

    report = check_report_from_result(result_with(assessment)).model_dump(
        mode="json", by_alias=True
    )

    [file] = report["no-review"]
    assert file["rating"] == expected
    assert file["unrated"] is False


def test_reports_the_matching_path_rule() -> None:
    rule = PathRule.fake()
    assessment = FileAssessment.fake().model_copy(update={"path_rule": rule})
    expected = {"pattern": rule.pattern.root, "probability": rule.probability.root}

    report = check_report_from_result(result_with(assessment)).model_dump(
        mode="json", by_alias=True
    )

    [file] = report["no-review"]
    assert file["path_rule"] == expected


def test_reports_the_sampling_evidence_and_effective_probability() -> None:
    sampling = AdaptiveSampling.fake()
    result = CheckResult.fake().model_copy(update={"sampling": sampling})
    expected = {
        "base_probability": sampling.base_probability.root,
        "base_probability_weight": sampling.weight.root,
        "commented_files": sampling.evidence.commented_files.root,
        "viewed_files": sampling.evidence.viewed_files.root,
        "effective_probability": sampling.effective_probability().root,
    }

    report = check_report_from_result(result).model_dump(mode="json", by_alias=True)

    assert report["sampling"] == expected
