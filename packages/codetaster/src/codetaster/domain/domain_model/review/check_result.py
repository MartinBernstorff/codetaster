from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.review.changes import (
    CommitSha,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.sampling import FileAssessments, Verdict


class CheckResult(BaseModel):
    """Which of the committed changes need human review."""

    model_config = ConfigDict(frozen=True)

    base: RevisionName
    merge_base: CommitSha
    head: CommitSha
    assessments: FileAssessments
    working_tree: WorkingTreeState

    @staticmethod
    def fake() -> CheckResult:
        return CheckResult(
            base=RevisionName.fake(),
            merge_base=CommitSha.fake(),
            head=CommitSha("2" * 40),
            assessments=FileAssessments.fake(),
            working_tree=WorkingTreeState.CLEAN,
        )

    def verdict(self) -> Verdict:
        """Needs review if any file does."""
        if any(
            assessment.verdict is Verdict.NEEDS_REVIEW
            for assessment in self.assessments.root
        ):
            return Verdict.NEEDS_REVIEW
        return Verdict.NO_REVIEW
