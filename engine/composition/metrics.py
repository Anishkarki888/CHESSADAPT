"""
Composite scoring for ChessAdapt benchmark.

Implements the three-pillar metric system from the benchmark blueprint:
  • Compliance Rate   (weight 0.50)
  • Inhibition Score  (weight 0.30)
  • Flexibility Index (weight 0.20)

All functions accept the event logs produced by StateTrackingMixin.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, asdict
from typing import Sequence

from engine.composition.mixins import MoveEvent


# ── Weights (from benchmark blueprint §03) ───────────────────────────────────
W_COMPLIANCE = 0.50
W_INHIBITION = 0.30
W_FLEXIBILITY = 0.20


@dataclass
class MetacognitionBreakdown:
    """Container for self-awareness and calibration metrics."""

    calibration_error: float
    error_detection_accuracy: float
    overconfidence_rate: float
    underconfidence_rate: float
    prospective_gap: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoreBreakdown:
    """Typed container for a full composite score result."""

    compliance_rate: float
    inhibition_score: float
    flexibility_index: float
    composite_score: float
    total_moves: int
    legal_moves: int
    inhibition_failures: int
    metacognition: MetacognitionBreakdown | None = None  # NEW

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.metacognition:
            d["metacognition"] = self.metacognition.to_dict()
        return d


# ── Metacognition metric functions ───────────────────────────────────────────

def calibration_error(events: Sequence[MoveEvent]) -> float:
    """Average |confidence/10 - correctness|."""
    vals = []
    for e in events:
        conf = e.extra.get("confidence")
        if conf is not None:
            vals.append(abs((conf / 10.0) - float(e.is_legal_perturbed)))
    return sum(vals) / len(vals) if vals else 0.0


def error_detection_accuracy(events: Sequence[MoveEvent]) -> float:
    """Fraction of times legal_prediction matched actual correctness."""
    matches = 0
    total = 0
    for e in events:
        pred = e.extra.get("legal_prediction")
        if pred is not None:
            total += 1
            if pred == e.is_legal_perturbed:
                matches += 1
    return matches / total if total > 0 else 0.0


# ── Individual metric functions ──────────────────────────────────────────────

def compliance_rate(events: Sequence[MoveEvent]) -> float:
# ... (rest of the file follows)
    """
    Fraction of model-generated moves that are legal under the perturbed
    ruleset.  Primary signal — directly measures whether the model
    applied the new rule.

    Returns 0.0 when there are no events.
    """
    if not events:
        return 0.0
    legal_count = sum(1 for e in events if e.is_legal_perturbed)
    return legal_count / len(events)


def inhibition_score(events: Sequence[MoveEvent]) -> float:
    """
    One minus the fraction of moves that would be legal under standard
    chess but are **illegal** under the perturbation.  Directly measures
    failure to suppress the memorized prior.

    A perfect score (1.0) means the model never fell back on standard rules.
    Returns 1.0 when there are no events (nothing to inhibit).
    """
    if not events:
        return 1.0
    failure_count = sum(1 for e in events if e.is_inhibition_failure)
    return 1.0 - (failure_count / len(events))


def flexibility_index(
    events_by_category: dict[str, Sequence[MoveEvent]],
) -> float:
    """
    Compliance-rate variance normalized across perturbation categories.
    A flexible model maintains performance across movement, win-condition,
    and turn-structure perturbations.

    Returns 1.0 when there is only one category or zero variance (perfect
    flexibility).  Lower scores indicate uneven performance across categories.

    Computation:
        1. Compute per-category compliance rates.
        2. Compute the population standard deviation.
        3. Flexibility = 1.0 − stdev  (clamped to [0, 1]).
    """
    if len(events_by_category) <= 1:
        return 1.0

    rates = [compliance_rate(evts) for evts in events_by_category.values()]

    if len(rates) < 2:
        return 1.0

    stdev = statistics.pstdev(rates)  # population stdev ∈ [0, 0.5]
    return max(0.0, min(1.0, 1.0 - stdev))


def composite_score(
    compliance: float,
    inhibition: float,
    flexibility: float,
) -> float:
    """
    Weighted composite:
        Score = 0.50 × Compliance + 0.30 × Inhibition + 0.20 × Flexibility
    """
    return (
        W_COMPLIANCE * compliance
        + W_INHIBITION * inhibition
        + W_FLEXIBILITY * flexibility
    )


# ── Convenience: compute everything from a flat event list ───────────────────

class MetacognitionCalculator:
    """Calculates all calibration and self-awareness scores."""

    @staticmethod
    def compute(events: Sequence[MoveEvent]) -> MetacognitionBreakdown:
        # Calibration Error
        ce = calibration_error(events)
        
        # Error Detection
        eda = error_detection_accuracy(events)

        # Over/Under-confidence
        over, under = 0, 0
        total_conf = 0

        for e in events:
            conf = e.extra.get("confidence")
            if conf is not None:
                total_conf += 1
                if conf >= 8 and not e.is_legal_perturbed:
                    over += 1
                if conf <= 3 and e.is_legal_perturbed:
                    under += 1
        
        over_rate  = over / total_conf if total_conf > 0 else 0.0
        under_rate = under / total_conf if total_conf > 0 else 0.0

        # Prospective Gap (Hard T1 items only)
        gaps = []
        for e in events:
            pre  = e.extra.get("pre_difficulty")
            conf = e.extra.get("confidence")
            if pre is not None and conf is not None:
                gaps.append(abs(pre - (10 - conf)))
        
        avg_gap = sum(gaps) / len(gaps) if gaps else None

        return MetacognitionBreakdown(
            calibration_error        = round(ce, 4),
            error_detection_accuracy = round(eda, 4),
            overconfidence_rate      = round(over_rate, 4),
            underconfidence_rate     = round(under_rate, 4),
            prospective_gap          = round(avg_gap, 4) if avg_gap is not None else None
        )


class MetricsCalculator:
    """
    Stateless calculator that accepts event logs and returns a
    ``ScoreBreakdown``.
    """

    @staticmethod
    def compute(
        events: Sequence[MoveEvent],
        events_by_category: dict[str, Sequence[MoveEvent]] | None = None,
        include_metacognition: bool = False,
    ) -> ScoreBreakdown:
        """
        Compute all metrics and the composite score.
        """
        # auto-group if not provided
        if events_by_category is None:
            grouped: dict[str, list[MoveEvent]] = {}
            for evt in events:
                grouped.setdefault(evt.category, []).append(evt)
            events_by_category = grouped

        c = compliance_rate(events)
        i = inhibition_score(events)
        f = flexibility_index(events_by_category)
        s = composite_score(c, i, f)

        meta = None
        if include_metacognition:
            meta = MetacognitionCalculator.compute(events)

        return ScoreBreakdown(
            compliance_rate     = round(c, 4),
            inhibition_score    = round(i, 4),
            flexibility_index   = round(f, 4),
            composite_score     = round(s, 4),
            total_moves         = len(events),
            legal_moves         = sum(1 for e in events if e.is_legal_perturbed),
            inhibition_failures = sum(1 for e in events if e.is_inhibition_failure),
            metacognition       = meta
        )
