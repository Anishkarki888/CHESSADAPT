"""
Post-evaluation results analysis and reporting.

Loads experiment results, computes aggregate statistics, produces
markdown tables, and verifies the performance gradient across models
and difficulty tiers.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluation.llm_client import MODEL_CONFIGS

logger = logging.getLogger("chessadapt.analysis")

DEFAULT_RESULTS_DIR = "data/results"


class ResultsAnalyzer:
    """
    Analyze benchmark results across models.

    Usage::

        analyzer = ResultsAnalyzer("data/results")
        report = analyzer.full_report()
        analyzer.save_report("data/results/report.md")
    """

    def __init__(self, results_dir: str | Path = DEFAULT_RESULTS_DIR) -> None:
        self._results_dir = Path(results_dir)
        self._model_summaries: dict[str, dict] = {}
        self._model_results: dict[str, list[dict]] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load run_summary.json and checkpoint.jsonl for each model."""
        if not self._results_dir.exists():
            logger.warning("Results directory not found: %s", self._results_dir)
            return

        for model_dir in sorted(self._results_dir.iterdir()):
            if not model_dir.is_dir():
                continue

            model_key = model_dir.name
            summary_path = model_dir / "run_summary.json"
            checkpoint_path = model_dir / "checkpoint.jsonl"

            if summary_path.exists():
                with open(summary_path, "r") as f:
                    self._model_summaries[model_key] = json.load(f)
                logger.info("Loaded summary for %s", model_key)

            if checkpoint_path.exists():
                results = []
                with open(checkpoint_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            results.append(json.loads(line))
                self._model_results[model_key] = results
                logger.info("Loaded %d results for %s", len(results), model_key)

    # ── Aggregate tables ─────────────────────────────────────────────────

    def model_comparison_table(self) -> str:
        """
        Generate a markdown table comparing all models on core metrics.

        | Model | Tier | Compliance | Inhibition | Flexibility | Composite |
        """
        if not self._model_summaries:
            return "_No results available._"

        rows = []
        for model_key, summary in sorted(self._model_summaries.items()):
            config = MODEL_CONFIGS.get(model_key)
            name = config.name if config else model_key
            tier = config.tier if config else "?"

            exp = summary.get("experiment_summary", {})
            rows.append({
                "model": name,
                "tier": tier,
                "compliance": exp.get("avg_compliance", 0),
                "inhibition": exp.get("avg_inhibition", 0),
                "flexibility": exp.get("avg_flexibility", 0),
                "composite": exp.get("avg_composite", 0),
                "evaluated": summary.get("evaluated", 0),
            })

        # Sort by composite score descending
        rows.sort(key=lambda r: r["composite"], reverse=True)

        lines = [
            "| Rank | Model | Tier | Tasks | Compliance | Inhibition | Flexibility | **Composite** |",
            "|:--:|:--|:--:|:--:|:--:|:--:|:--:|:--:|",
        ]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"| {i} | {r['model']} | {r['tier']} | {r['evaluated']} | "
                f"{r['compliance']:.3f} | {r['inhibition']:.3f} | "
                f"{r['flexibility']:.3f} | **{r['composite']:.3f}** |"
            )

        return "\n".join(lines)

    def per_perturbation_table(self) -> str:
        """
        Breakdown of compliance rate per perturbation rule across models.

        | Rule | GPT-4o | Claude | Gemini | ... |
        """
        if not self._model_results:
            return "_No detailed results available._"

        # Collect per-rule, per-model compliance
        rule_model_scores: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for model_key, results in self._model_results.items():
            for r in results:
                for rule in r.get("rule_names", []):
                    score = r.get("score", {})
                    compliance = score.get("compliance_rate", 0)
                    rule_model_scores[rule][model_key].append(compliance)

        if not rule_model_scores:
            return "_No per-rule results available._"

        models = sorted(self._model_results.keys())
        model_names = []
        for m in models:
            config = MODEL_CONFIGS.get(m)
            model_names.append(config.name if config else m)

        header = "| Rule | " + " | ".join(model_names) + " |"
        separator = "|:--|" + "|".join(":--:" for _ in models) + "|"

        lines = [header, separator]
        for rule in sorted(rule_model_scores.keys()):
            cols = [rule]
            for model_key in models:
                scores = rule_model_scores[rule].get(model_key, [])
                if scores:
                    avg = sum(scores) / len(scores)
                    cols.append(f"{avg:.3f}")
                else:
                    cols.append("—")
            lines.append("| " + " | ".join(cols) + " |")

        return "\n".join(lines)

    def difficulty_breakdown_table(self) -> str:
        """
        Compliance rate by difficulty tier across models.

        | Difficulty | GPT-4o | Claude | Gemini | ... |
        """
        if not self._model_results:
            return "_No detailed results available._"

        tier_model_scores: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for model_key, results in self._model_results.items():
            for r in results:
                tier = r.get("difficulty_tier", "unknown")
                compliance = r.get("score", {}).get("compliance_rate", 0)
                tier_model_scores[tier][model_key].append(compliance)

        models = sorted(self._model_results.keys())
        model_names = [
            MODEL_CONFIGS[m].name if m in MODEL_CONFIGS else m
            for m in models
        ]

        header = "| Difficulty | " + " | ".join(model_names) + " |"
        separator = "|:--|" + "|".join(":--:" for _ in models) + "|"

        lines = [header, separator]
        for tier in ["easy", "medium", "hard"]:
            cols = [tier.capitalize()]
            for model_key in models:
                scores = tier_model_scores[tier].get(model_key, [])
                if scores:
                    avg = sum(scores) / len(scores)
                    cols.append(f"{avg:.3f}")
                else:
                    cols.append("—")
            lines.append("| " + " | ".join(cols) + " |")

        return "\n".join(lines)

    def task_type_breakdown_table(self) -> str:
        """Composite score by task type (T1/T2/T3) across models."""
        if not self._model_results:
            return "_No detailed results available._"

        type_model_scores: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for model_key, results in self._model_results.items():
            for r in results:
                tt = r.get("task_type", "?")
                comp = r.get("score", {}).get("composite_score", 0)
                type_model_scores[tt][model_key].append(comp)

        models = sorted(self._model_results.keys())
        model_names = [
            MODEL_CONFIGS[m].name if m in MODEL_CONFIGS else m
            for m in models
        ]

        header = "| Task Type | " + " | ".join(model_names) + " |"
        separator = "|:--|" + "|".join(":--:" for _ in models) + "|"

        lines = [header, separator]
        for tt in ["T1", "T2", "T3"]:
            cols = [tt]
            for model_key in models:
                scores = type_model_scores[tt].get(model_key, [])
                if scores:
                    avg = sum(scores) / len(scores)
                    cols.append(f"{avg:.3f}")
                else:
                    cols.append("—")
            lines.append("| " + " | ".join(cols) + " |")

        return "\n".join(lines)

    # ── Gradient verification ────────────────────────────────────────────

    def verify_gradient(self) -> dict[str, Any]:
        """
        Verify that performance follows the expected gradient:
        frontier > mid > weak across difficulty tiers.

        Returns a dict with gradient check results.
        """
        if not self._model_summaries:
            return {"verified": False, "reason": "No results available"}

        # Group models by tier
        tier_scores: dict[str, list[float]] = defaultdict(list)
        for model_key, summary in self._model_summaries.items():
            config = MODEL_CONFIGS.get(model_key)
            if not config:
                continue
            composite = summary.get("experiment_summary", {}).get("avg_composite", 0)
            tier_scores[config.tier].append(composite)

        # Compute tier averages
        tier_avgs = {}
        for tier, scores in tier_scores.items():
            tier_avgs[tier] = sum(scores) / len(scores) if scores else 0

        # Check gradient: frontier >= mid >= weak
        frontier = tier_avgs.get("frontier", 0)
        mid = tier_avgs.get("mid", 0)
        weak = tier_avgs.get("weak", 0)

        gradient_holds = frontier >= mid >= weak

        return {
            "verified": gradient_holds,
            "tier_averages": tier_avgs,
            "frontier_avg": round(frontier, 4),
            "mid_avg": round(mid, 4),
            "weak_avg": round(weak, 4),
            "models_per_tier": {
                tier: len(scores) for tier, scores in tier_scores.items()
            },
        }

    # ── Full report ──────────────────────────────────────────────────────

    def full_report(self) -> str:
        """Generate a full markdown analysis report."""
        gradient = self.verify_gradient()
        gradient_status = "✅ Verified" if gradient["verified"] else "⚠️ Not verified"

        sections = [
            "# ChessAdapt Benchmark — Results Report\n",
            "## Model Comparison\n",
            self.model_comparison_table(),
            "\n## Gradient Verification\n",
            f"**Status**: {gradient_status}\n",
            f"- Frontier average: {gradient['frontier_avg']:.3f}",
            f"- Mid-tier average: {gradient['mid_avg']:.3f}",
            f"- Weak-tier average: {gradient['weak_avg']:.3f}\n",
            "## Per-Perturbation Breakdown\n",
            self.per_perturbation_table(),
            "\n## Difficulty Tier Breakdown\n",
            self.difficulty_breakdown_table(),
            "\n## Task Type Breakdown\n",
            self.task_type_breakdown_table(),
        ]
        return "\n".join(sections)

    def save_report(self, path: str | Path | None = None) -> Path:
        """Save the full report as a markdown file."""
        if path is None:
            path = self._results_dir / "report.md"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.full_report(), encoding="utf-8")
        logger.info("Report saved to %s", path)
        return path
