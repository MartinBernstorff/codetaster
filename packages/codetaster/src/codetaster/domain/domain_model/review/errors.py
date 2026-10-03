from codetaster.domain.domain_model.review.changes import RevisionName


class UnknownRevisionError(Exception):
    """`revision` does not name a commit in the repository."""

    def __init__(self, revision: RevisionName) -> None:
        super().__init__(f"{revision} does not name a commit")
        self.revision = revision

    @staticmethod
    def fake() -> UnknownRevisionError:
        return UnknownRevisionError(RevisionName.fake())
