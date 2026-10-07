from typing import Annotated

from pydantic import ConfigDict, Field, RootModel


class TopRatedPercentage(RootModel[Annotated[int, Field(ge=0, le=100)]]):
    """The percentage, from 0 to 100, of changed files that need review.

    The files with the highest AI ratings are picked.
    """

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> TopRatedPercentage:
        return TopRatedPercentage(20)
