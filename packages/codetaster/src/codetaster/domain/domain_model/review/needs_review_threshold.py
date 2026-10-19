from typing import Annotated

from pydantic import ConfigDict, Field, RootModel


class NeedsReviewThreshold(RootModel[Annotated[float, Field(ge=0, le=1)]]):
    """The AI rating, from 0 to 1, at or above which a changed file needs review."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> NeedsReviewThreshold:
        return NeedsReviewThreshold(0.5)
