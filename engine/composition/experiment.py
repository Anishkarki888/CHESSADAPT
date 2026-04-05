"""
ExperimentRunner — orchestrates evaluation of model responses against
ChessAdapt benchmark tasks, with full JSON-based experiment tracking.

Supports T1 (single rule, one move), T2 (single rule, best move), and
T3 (stacked rules, 3-move sequence) task types.

Every experiment is logged as structured JSON to ``data/experiments/``
with timestamps, unique experiment IDs, and full event traces.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Sequence

import chess

from engine.composition.composer import RuleComposer
from engine.composition.metrics import MetricsCalculator, ScoreBreakdown
from engine.composition.mixins import MoveEvent

# ── Output directory ─────────────────────────────────────────────────────────
EXPERIMENT_DIR = Path("data/experiments")


@dataclass
class ExperimentResult:
    """Typed container for a single experiment evaluation."""

    experiment_id: str
    timestamp: float
    task_type: str  # T1 | T2 | T3
    fen: str
    rule_names: list[str]
    model_moves: list[str]
    per_move_results: list[dict[str, Any]]
    score: ScoreBreakdown
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


class ExperimentRunner:
    """
    Orchestrates benchmark evaluation.

    Usage::

        runner = ExperimentRunner()
        result = runner.run_single(
            fen="...",
            rule_names=["bishop_as_rook"],
            model_moves=["e2e4"],
            task_type="T1",
        )
        print(result.score.composite_score)

    For batch evaluation::

        results = runner.run_batch([
            {"fen": "...", "rule_names": [...], "model_moves": [...], "task_type": "T1"},
            ...
        ])
    """

    def __init__(
        self,
        output_dir: str | Path = EXPERIMENT_DIR,
        save_to_disk: bool = True,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._save_to_disk = save_to_disk
        self._calc = MetricsCalculator()
        self._results: list[ExperimentResult] = []

        if self._save_to_disk:
            self._output_dir.mkdir(parents=True, exist_ok=True)

    # ── Single experiment ────────────────────────────────────────────────

    def run_single(
        self,
        fen: str,
        rule_names: list[str],
        model_moves: list[str],
        task_type: str = "T1",
        metadata: dict[str, Any] | None = None,
        meta_scoring: dict[str, Any] | None = None,
    ) -> ExperimentResult:
        """
        Evaluate a model's response against a single benchmark task.
        """
        experiment_id = uuid.uuid4().hex[:16]
        timestamp = time.time()
        meta = metadata or {}
        meta_scoring = meta_scoring or {}

        composer = RuleComposer(fen, rule_names)
        per_move_results: list[dict[str, Any]] = []

        for i, uci in enumerate(model_moves):
            # Validate the move (records event internally)
            # Pass meta_scoring into the first move's event
            extra = meta_scoring if i == 0 else {}
            result = composer.validate_move(uci, **extra)
            result["move_index"] = i
            per_move_results.append(result)

            # For T3 sequences: push legal moves
            if result["legal"] and task_type == "T3" and i < len(model_moves) - 1:
                try:
                    composer.push(uci)
                except ValueError:
                    pass

        # Compute composite score from the event log
        events = composer.get_event_log()
        scoring_events = events[:len(model_moves)]

        score = self._calc.compute(
            scoring_events, 
            include_metacognition=bool(meta_scoring)
        )

        result_obj = ExperimentResult(
            experiment_id=experiment_id,
            timestamp=timestamp,
            task_type=task_type,
            fen=fen,
            rule_names=list(rule_names),
            model_moves=list(model_moves),
            per_move_results=per_move_results,
            score=score,
            metadata=meta,
        )

        self._results.append(result_obj)
        if self._save_to_disk:
            self._save_result(result_obj)

        return result_obj

    # ── Batch evaluation ─────────────────────────────────────────────────

    def run_batch(
        self,
        tasks: Sequence[dict[str, Any]],
    ) -> list[ExperimentResult]:
        """
        Evaluate a batch of tasks.

        Each task dict must contain: ``fen``, ``rule_names``, ``model_moves``,
        ``task_type``.  Optional: ``metadata``.

        Returns a list of ``ExperimentResult`` in the same order.
        """
        results = []
        for i, task in enumerate(tasks):
            try:
                result = self.run_single(
                    fen=task["fen"],
                    rule_names=task["rule_names"],
                    model_moves=task["model_moves"],
                    task_type=task.get("task_type", "T1"),
                    metadata=task.get("metadata", {"batch_index": i}),
                )
                results.append(result)
            except Exception as e:
                # Create a failed result rather than crashing the batch
                error_result = ExperimentResult(
                    experiment_id=uuid.uuid4().hex[:16],
                    timestamp=time.time(),
                    task_type=task.get("task_type", "T1"),
                    fen=task.get("fen", ""),
                    rule_names=task.get("rule_names", []),
                    model_moves=task.get("model_moves", []),
                    per_move_results=[],
                    score=ScoreBreakdown(
                        compliance_rate=0.0,
                        inhibition_score=0.0,
                        flexibility_index=0.0,
                        composite_score=0.0,
                        total_moves=0,
                        legal_moves=0,
                        inhibition_failures=0,
                    ),
                    metadata={
                        **task.get("metadata", {}),
                        "error": str(e),
                        "batch_index": i,
                    },
                )
                results.append(error_result)

        return results

    # ── Aggregation ──────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """
        Return aggregate statistics over all experiments run so far.
        """
        if not self._results:
            return {"total_experiments": 0}

        scores = [r.score for r in self._results]
        
        agg = {
            "total_experiments": len(self._results),
            "avg_compliance": round(
                sum(s.compliance_rate for s in scores) / len(scores), 4
            ),
            "avg_inhibition": round(
                sum(s.inhibition_score for s in scores) / len(scores), 4
            ),
            "avg_flexibility": round(
                sum(s.flexibility_index for s in scores) / len(scores), 4
            ),
            "avg_composite": round(
                sum(s.composite_score for s in scores) / len(scores), 4
            ),
            "total_moves_evaluated": sum(s.total_moves for s in scores),
            "total_legal_moves": sum(s.legal_moves for s in scores),
            "total_inhibition_failures": sum(
                s.inhibition_failures for s in scores
            ),
        }

        # ── Metacognition aggregates ──
        meta_scores = [s.metacognition for s in scores if s.metacognition]
        if meta_scores:
            n = len(meta_scores)
            agg["metacognition"] = {
                "avg_calibration_error": round(sum(m.calibration_error for m in meta_scores) / n, 4),
                "avg_error_detection": round(sum(m.error_detection_accuracy for m in meta_scores) / n, 4),
                "avg_overconfidence": round(sum(m.overconfidence_rate for m in meta_scores) / n, 4),
                "avg_underconfidence": round(sum(m.underconfidence_rate for m in meta_scores) / n, 4),
            }
            # average prospective gap if available
            gaps = [m.prospective_gap for m in meta_scores if m.prospective_gap is not None]
            if gaps:
                agg["metacognition"]["avg_prospective_gap"] = round(sum(gaps) / len(gaps), 4)

        agg["by_task_type"] = self._group_by_task_type()
        return agg

    def _group_by_task_type(self) -> dict[str, dict[str, Any]]:
        """Group results by task type and compute per-group averages."""
        groups: dict[str, list[ExperimentResult]] = {}
        for r in self._results:
            groups.setdefault(r.task_type, []).append(r)

        summary: dict[str, dict[str, Any]] = {}
        for task_type, results in groups.items():
            scores = [r.score for r in results]
            n = len(scores)
            summary[task_type] = {
                "count": n,
                "avg_compliance": round(
                    sum(s.compliance_rate for s in scores) / n, 4
                ),
                "avg_composite": round(
                    sum(s.composite_score for s in scores) / n, 4
                ),
            }
        return summary

    # ── Persistence ──────────────────────────────────────────────────────

    def _save_result(self, result: ExperimentResult) -> Path:
        """Save a single experiment result as a JSON file."""
        filename = (
            f"{result.experiment_id}_"
            f"{result.task_type}_"
            f"{'_'.join(result.rule_names)}.json"
        )
        path = self._output_dir / filename
        path.write_text(result.to_json(), encoding="utf-8")
        return path

    def save_summary(self, path: str | Path | None = None) -> Path:
        """Save the aggregate summary to a JSON file."""
        if path is None:
            path = self._output_dir / "summary.json"
        path = Path(path)
        path.write_text(
            json.dumps(self.summary(), indent=2, default=str),
            encoding="utf-8",
        )
        return path

    @property
    def results(self) -> list[ExperimentResult]:
        """All experiment results collected so far."""
        return list(self._results)
