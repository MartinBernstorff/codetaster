"""The `--format json` output of `codetaster check`."""

from pydantic import BaseModel, ConfigDict, Field, RootModel

from codetaster.domain.domain_model.review.changes import (
    ChangeType,
    CommitSha,
    RepositoryPath,
    RevisionName,
)
from codetaster.domain.domain_model.review.check_result import CheckResult
from codetaster.domain.domain_model.review.sampling import (
    Draw,
    FileAssessment,
    Probability,
    Verdict,
)


class SchemaVersion(RootModel[int]):
    """Bumped when a field is removed or changes meaning. Adding a field keeps it."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> SchemaVersion:
        return SchemaVersion(1)


class ReportFlag(RootModel[bool]):
    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> ReportFlag:
        return ReportFlag(root=False)


class BaseReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: RevisionName
    merge_base: CommitSha

    @staticmethod
    def fake() -> BaseReport:
        return BaseReport(ref=RevisionName.fake(), merge_base=CommitSha.fake())


class HeadReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    commit: CommitSha

    @staticmethod
    def fake() -> HeadReport:
        return HeadReport(commit=CommitSha.fake())


class FileReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: RepositoryPath
    previous_path: RepositoryPath | None
    change_type: ChangeType
    base_probability: Probability
    probability: Probability
    draw: Draw

    @staticmethod
    def fake() -> FileReport:
        return file_report_from_assessment(FileAssessment.fake())


class CheckReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: SchemaVersion
    needs_review: ReportFlag
    override_label_applied: ReportFlag
    base: BaseReport
    head: HeadReport
    needs_review_files: tuple[FileReport, ...] = Field(
        serialization_alias="needs-review"
    )
    no_review_files: tuple[FileReport, ...] = Field(serialization_alias="no-review")

    @staticmethod
    def fake() -> CheckReport:
        return check_report_from_result(CheckResult.fake())


def check_report_from_result(result: CheckResult) -> CheckReport:
    def files_with(verdict: Verdict) -> tuple[FileReport, ...]:
        return tuple(
            file_report_from_assessment(assessment)
            for assessment in result.assessments.root
            if assessment.verdict is verdict
        )

    return CheckReport(
        schema_version=SchemaVersion(1),
        needs_review=ReportFlag(root=result.verdict() is Verdict.NEEDS_REVIEW),
        # Nothing applies an override label yet.
        override_label_applied=ReportFlag(root=False),
        base=BaseReport(ref=result.base, merge_base=result.merge_base),
        head=HeadReport(commit=result.head),
        needs_review_files=files_with(Verdict.NEEDS_REVIEW),
        no_review_files=files_with(Verdict.NO_REVIEW),
    )


def file_report_from_assessment(assessment: FileAssessment) -> FileReport:
    return FileReport(
        path=assessment.change.path(),
        previous_path=assessment.change.previous_path(),
        change_type=assessment.change.change_type(),
        base_probability=assessment.base_probability,
        probability=assessment.probability,
        draw=assessment.draw,
    )
