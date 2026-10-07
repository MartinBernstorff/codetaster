from typing import Annotated

from pydantic import ConfigDict, Field, RootModel


class Probability(RootModel[Annotated[float, Field(ge=0, le=1)]]):
    """A file's chance, from 0 to 1, of needing human review."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> Probability:
        return Probability(0.5)
