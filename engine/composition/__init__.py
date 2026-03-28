"""
engine.composition — rule stacking, experiment tracking, and scoring.

Public API
----------
RuleComposer       : Stack multiple perturbation rules on a single board.
ExperimentRunner   : Evaluate model responses with full JSON experiment logs.
MetricsCalculator  : Compute compliance, inhibition, flexibility, composite.
LoggingMixin       : Structured rotating-file + console logging mixin.
StateTrackingMixin : Append-only MoveEvent log for post-experiment analysis.
MoveEvent          : Dataclass representing a single board interaction event.
ScoreBreakdown     : Typed container for composite score results.
ExperimentResult   : Typed container for a single experiment evaluation.
"""

from engine.composition.mixins import (
    LoggingMixin,
    StateTrackingMixin,
    MoveEvent,
)
from engine.composition.metrics import (
    MetricsCalculator,
    ScoreBreakdown,
    compliance_rate,
    inhibition_score,
    flexibility_index,
    composite_score,
)
from engine.composition.composer import RuleComposer
from engine.composition.experiment import ExperimentRunner, ExperimentResult

__all__ = [
    "RuleComposer",
    "ExperimentRunner",
    "ExperimentResult",
    "MetricsCalculator",
    "ScoreBreakdown",
    "LoggingMixin",
    "StateTrackingMixin",
    "MoveEvent",
    "compliance_rate",
    "inhibition_score",
    "flexibility_index",
    "composite_score",
]
