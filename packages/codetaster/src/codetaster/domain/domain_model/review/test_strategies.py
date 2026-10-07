"""Hypothesis strategies for review models, shared by the tests in this folder."""

from hypothesis import strategies as st

from codetaster.domain.domain_model.review.changes import (
    BlobSha,
    FileChange,
    FileVersion,
    RepositoryPath,
)
from codetaster.domain.domain_model.review.sampling import Probability


def file_versions() -> st.SearchStrategy[FileVersion]:
    return st.builds(
        FileVersion,
        path=st.builds(
            RepositoryPath,
            st.from_regex(r"[a-z]{1,8}(/[a-z]{1,8})*\.py", fullmatch=True),
        ),
        blob=st.builds(BlobSha, st.from_regex(r"[0-9a-f]{40}", fullmatch=True)),
    )


def file_changes() -> st.SearchStrategy[FileChange]:
    return st.one_of(
        st.builds(FileChange, before=st.none(), after=file_versions()),
        st.builds(FileChange, before=file_versions(), after=st.none()),
        st.builds(FileChange, before=file_versions(), after=file_versions()),
    )


def probabilities() -> st.SearchStrategy[Probability]:
    return st.builds(Probability, st.floats(min_value=0, max_value=1))
