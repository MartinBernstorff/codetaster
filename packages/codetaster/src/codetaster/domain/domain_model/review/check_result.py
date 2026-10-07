from pydantic import BaseModel, ConfigDict

from codetaster.domain.domain_model.review.changes import (
    CommitSha,
    RevisionName,
    WorkingTreeState,
)
from codetaster.domain.domain_model.review.ratings_validation import (
    InvalidRatingsFile,
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
    ratings_problem: InvalidRatingsFile | None
    """Why the ratings file was ignored, leaving every file unrated."""

    @staticmethod
    def fake() -> CheckResult:
        return CheckResult(
            base=RevisionName.fake(),
            merge_base=CommitSha.fake(),
            head=CommitSha.fake(),
            assessments=FileAssessments.fake(),
            working_tree=WorkingTreeState.CLEAN,
            ratings_problem=None,
        )

    def verdict(self) -> Verdict:
        """The most urgent group any file is in, or no-review without files."""
        present = {assessment.verdict for assessment in self.assessments.root}
        return next(
            (verdict for verdict in Verdict if verdict in present), Verdict.NO_REVIEW
        )

    def assessments_with(self, verdict: Verdict) -> FileAssessments:
        return FileAssessments(
            tuple(
                assessment
                for assessment in self.assessments.root
                if assessment.verdict is verdict
            )
        )
