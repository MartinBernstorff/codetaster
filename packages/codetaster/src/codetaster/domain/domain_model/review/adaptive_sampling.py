"""Adaptive sampling: the reviewer's comments raise the sampling probability.

The base probability is the mean of a Beta prior worth `weight` reviewed files.
Each reviewed file with a comment counts as a defect, each viewed file without
one as clean, and the posterior mean, never below the base probability, is the
effective probability. Every file's base probability is then scaled by the same
odds ratio as the base probability was.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, RootModel

from codetaster.domain.domain_model.review.probability import Probability


class CommentedFileCount(RootModel[Annotated[int, Field(ge=0)]]):
    """Sampled or needs-review files with a comment thread by the reviewer."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> CommentedFileCount:
        return CommentedFileCount(1)


class ViewedFileCount(RootModel[Annotated[int, Field(ge=0)]]):
    """Sampled or needs-review files the reviewer viewed without commenting."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> ViewedFileCount:
        return ViewedFileCount(1)


class BaseProbabilityWeight(RootModel[Annotated[float, Field(gt=0)]]):
    """How many reviewed files the base probability counts as."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def fake() -> BaseProbabilityWeight:
        return BaseProbabilityWeight(10)


class SamplingEvidence(BaseModel):
    """What the reviewer found in the files they reviewed so far."""

    model_config = ConfigDict(frozen=True)

    commented_files: CommentedFileCount
    viewed_files: ViewedFileCount

    @staticmethod
    def none() -> SamplingEvidence:
        return SamplingEvidence(
            commented_files=CommentedFileCount(0), viewed_files=ViewedFileCount(0)
        )

    @staticmethod
    def fake() -> SamplingEvidence:
        return SamplingEvidence(
            commented_files=CommentedFileCount.fake(),
            viewed_files=ViewedFileCount.fake(),
        )


class AdaptiveSampling(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_probability: Probability
    weight: BaseProbabilityWeight
    evidence: SamplingEvidence

    @staticmethod
    def fake() -> AdaptiveSampling:
        return AdaptiveSampling(
            base_probability=Probability(0.1),
            weight=BaseProbabilityWeight.fake(),
            evidence=SamplingEvidence.fake(),
        )

    def effective_probability(self) -> Probability:
        """The posterior mean, but never below the base probability."""
        base = self.base_probability.root
        weight = self.weight.root
        defects = self.evidence.commented_files.root
        clean = self.evidence.viewed_files.root
        posterior_mean = (base * weight + defects) / (weight + defects + clean)
        return Probability(max(posterior_mean, base))

    def adjusted(self, probability: Probability) -> Probability:
        """`probability` with its odds scaled as the base probability's were.

        0 and 1 stay as they are. So does everything if the base probability is
        0 or 1, or the effective probability equals it.
        """
        base = self.base_probability.root
        effective = self.effective_probability().root
        original = probability.root
        if effective == base or base in (0, 1) or original in (0, 1):
            return probability
        # r·odds(q) / (1 + r·odds(q)), with r = odds(effective) / odds(base),
        # multiplied out so that a tiny base probability does not overflow.
        raised = effective * (1 - base) * original
        denominator = base * (1 - effective) * (1 - original) + raised
        if denominator == 0:
            return probability
        # Rounding must not lower a probability or push it above 1.
        return Probability(min(1, max(original, raised / denominator)))
