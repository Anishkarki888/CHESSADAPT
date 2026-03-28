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
class ScoreBreakdown:
    """Typed container for a full composite score result."""

    compliance_rate: float
    inhibition_score: float
    flexibility_index: float
    composite_score: float
    total_moves: int
    legal_moves: int
    inhibition_failures: int

    def to_dict(self) -> dict:
        return asdict(self)


# ── Individual metric functions ──────────────────────────────────────────────

def compliance_rate(events: Sequence[MoveEvent]) -> float:
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

class MetricsCalculator:
    """
    Stateless calculator that accepts event logs and returns a
    ``ScoreBreakdown``.

    Usage::

        calc = MetricsCalculator()
        score = calc.compute(event_log)
        print(score.composite_score)
    """

    @staticmethod
    def compute(
        events: Sequence[MoveEvent],
        events_by_category: dict[str, Sequence[MoveEvent]] | None = None,
    ) -> ScoreBreakdown:
        """
        Compute all three metrics and the composite score.

        Parameters
        ----------
        events : list[MoveEvent]
            Flat list of all evaluation events.
        events_by_category : dict, optional
            Events grouped by perturbation category.  If ``None``, events
            are auto-grouped using ``MoveEvent.category``.
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

        return ScoreBreakdown(
            compliance_rate=round(c, 4),
            inhibition_score=round(i, 4),
            flexibility_index=round(f, 4),
            composite_score=round(s, 4),
            total_moves=len(events),
            legal_moves=sum(1 for e in events if e.is_legal_perturbed),
            inhibition_failures=sum(1 for e in events if e.is_inhibition_failure),
        )
