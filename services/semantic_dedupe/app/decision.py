from enum import Enum
from dataclasses import dataclass


class DedupeDecision(str, Enum):
    DUPLICATE = "duplicate"
    PROBABLE_DUPLICATE = "probable_duplicate"
    RELATED = "related"
    DISTINCT = "distinct"


@dataclass(frozen=True)
class DecisionBand:
    min_similarity: float
    decision: DedupeDecision


DECISION_BANDS = [
    DecisionBand(0.90, DedupeDecision.DUPLICATE),
    DecisionBand(0.80, DedupeDecision.PROBABLE_DUPLICATE),
    DecisionBand(0.65, DedupeDecision.RELATED),
    DecisionBand(0.00, DedupeDecision.DISTINCT),
]


def classify_similarity(similarity: float) -> DedupeDecision:
    for band in DECISION_BANDS:
        if similarity >= band.min_similarity:
            return band.decision
    return DedupeDecision.DISTINCT

