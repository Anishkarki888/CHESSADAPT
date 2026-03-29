"""
Benchmark evaluation runner.

Orchestrates the full pipeline: load tasks → call LLMs → parse
responses → score with ExperimentRunner → save results.

Supports resume from checkpoint and dry-run mode.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from evaluation.llm_client import LLMClient, create_client, MODEL_CONFIGS
from evaluation.prompt_builder import PromptBuilder
from evaluation.response_parser import ResponseParser
from evaluation.task_generator import TaskGenerator
from engine.composition.experiment import ExperimentRunner

logger = logging.getLogger("chessadapt.runner")

# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULT_TASKS_PATH = "data/tasks/tasks.jsonl"
DEFAULT_RESULTS_DIR = "data/results"


class BenchmarkRunner:
    """
    Orchestrates model evaluation against ChessAdapt benchmark tasks.

    Usage::

        runner = BenchmarkRunner(model_key="gpt-4o")
        runner.run(tasks_path="data/tasks/tasks.jsonl", max_tasks=50)
        print(runner.summary())

    Parameters
    ----------
    model_key : str
        Key from MODEL_CONFIGS (e.g. "gpt-4o", "claude-3.7-sonnet").
    results_dir : str | Path
        Base directory for results output.
    dry_run : bool
        If True, no API calls are made; prompts are printed instead.
    """

    def __init__(
        self,
        model_key: str,
        results_dir: str | Path = DEFAULT_RESULTS_DIR,
        dry_run: bool = False,
    ) -> None:
        self._model_key = model_key
        self._dry_run = dry_run
        self._results_dir = Path(results_dir) / model_key
        self._results_dir.mkdir(parents=True, exist_ok=True)

        self._parser = ResponseParser()
        self._experiment_runner = ExperimentRunner(
            output_dir=self._results_dir / "experiments",
            save_to_disk=True,
        )

        if not dry_run:
            self._client: LLMClient = create_client(model_key)
        else:
            self._client = None  # type: ignore

        self._completed_ids: set[str] = self._load_checkpoint()
        self._run_results: list[dict[str, Any]] = []

        config = MODEL_CONFIGS[model_key]
        logger.info(
            "BenchmarkRunner initialised | model=%s | tier=%s | dry_run=%s | checkpoint=%d",
            config.name, config.tier, dry_run, len(self._completed_ids),
        )

    # ── Checkpoint management ────────────────────────────────────────────

    def _checkpoint_path(self) -> Path:
        return self._results_dir / "checkpoint.jsonl"

    def _load_checkpoint(self) -> set[str]:
        """Load IDs of already-completed tasks for resume."""
        path = self._checkpoint_path()
        if not path.exists():
            return set()
        ids = set()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    ids.add(data.get("task_id", ""))
        logger.info("Loaded %d completed tasks from checkpoint", len(ids))
        return ids

    def _save_checkpoint_entry(self, task_id: str, result: dict) -> None:
        """Append a completed task to the checkpoint file."""
        with open(self._checkpoint_path(), "a", encoding="utf-8") as f:
            entry = {"task_id": task_id, **result}
            f.write(json.dumps(entry, default=str) + "\n")

    @staticmethod
    def _task_id(task: dict) -> str:
        """Generate a deterministic ID for a task (FEN + rules + type)."""
        rules = "+".join(sorted(task.get("rule_names", [])))
        return f"{task['fen']}|{rules}|{task['task_type']}"

    # ── Evaluation ───────────────────────────────────────────────────────

    def run(
        self,
        tasks_path: str | Path = DEFAULT_TASKS_PATH,
        max_tasks: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run evaluation on all tasks from the JSONL file.

        Parameters
        ----------
        tasks_path : str | Path
            Path to the tasks JSONL file.
        max_tasks : int, optional
            Limit number of tasks to evaluate (useful for testing).

        Returns
        -------
        list[dict]
            Per-task evaluation results.
        """
        tasks = TaskGenerator.load(tasks_path)
        if max_tasks is not None:
            tasks = tasks[:max_tasks]

        total = len(tasks)
        skipped = 0
        failed = 0

        logger.info(
            "Starting evaluation | model=%s | tasks=%d | checkpoint=%d",
            self._model_key, total, len(self._completed_ids),
        )

        for i, task in enumerate(tasks):
            task_id = self._task_id(task)

            # Skip already-completed tasks (resume)
            if task_id in self._completed_ids:
                skipped += 1
                continue

            logger.info(
                "[%d/%d] Evaluating %s | fen=%s | rules=%s",
                i + 1, total, task["task_type"],
                task["fen"][:30] + "...", task.get("rule_names", []),
            )

            try:
                result = self._evaluate_single(task)
                result["task_index"] = i
                self._run_results.append(result)

                self._completed_ids.add(task_id)
                self._save_checkpoint_entry(task_id, result)

            except Exception as exc:
                failed += 1
                logger.error(
                    "Task %d failed: %s", i, exc, exc_info=True
                )
                self._run_results.append({
                    "task_index": i,
                    "error": str(exc),
                    "task_type": task.get("task_type", ""),
                    "rule_names": task.get("rule_names", []),
                })

        # Save final summary
        self._save_run_summary(total, skipped, failed)

        logger.info(
            "Evaluation complete | total=%d | skipped=%d | failed=%d | evaluated=%d",
            total, skipped, failed, total - skipped - failed,
        )

        return self._run_results

    def _evaluate_single(self, task: dict) -> dict[str, Any]:
        """Evaluate a single task: prompt → LLM → parse → score."""
        prompt = task.get("prompt", "")
        rule_names = task.get("rule_names", [])
        
        # Extract rule name from rule_delta if rule_names is empty
        if not rule_names and "rule_delta" in task:
            rule_delta = task["rule_delta"]
            if "perturbation" in rule_delta:
                rule_names = [rule_delta["perturbation"]]
        
        if not prompt:
            prompt = PromptBuilder.build(
                task["fen"], rule_names, task["task_type"]
            )

        # Call the LLM (or dry-run)
        if self._dry_run:
            logger.info("DRY RUN | prompt_len=%d", len(prompt))
            raw_response = "[dry-run] e2e4"
        else:
            raw_response = self._client.generate(prompt, temperature=0.0)

        # Parse response
        task_type = task["task_type"]
        max_moves = 3 if task_type == "T3" else 1
        model_moves = self._parser.extract(raw_response, max_moves=max_moves)

        if not model_moves:
            model_moves = ["0000"]  # null move sentinel for scoring

        # Score via ExperimentRunner
        exp_result = self._experiment_runner.run_single(
            fen=task["fen"],
            rule_names=rule_names,
            model_moves=model_moves,
            task_type=task_type,
            metadata={
                "model": self._model_key,
                "raw_response": raw_response[:500],
                "difficulty_tier": task.get("difficulty_tier", ""),
            },
        )

        return {
            "task_type": task_type,
            "fen": task["fen"],
            "rule_names": rule_names,
            "difficulty_tier": task.get("difficulty_tier", ""),
            "model_moves": model_moves,
            "raw_response": raw_response[:500],
            "score": exp_result.score.to_dict(),
            "experiment_id": exp_result.experiment_id,
        }

    # ── Summary & persistence ────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Return aggregate summary of the experiment runner."""
        return self._experiment_runner.summary()

    def _save_run_summary(self, total: int, skipped: int, failed: int) -> None:
        """Save the run summary to a JSON file."""
        summary = {
            "model": self._model_key,
            "model_config": {
                "name": MODEL_CONFIGS[self._model_key].name,
                "tier": MODEL_CONFIGS[self._model_key].tier,
                "model_id": MODEL_CONFIGS[self._model_key].model_id,
            },
            "total_tasks": total,
            "skipped": skipped,
            "failed": failed,
            "evaluated": total - skipped - failed,
            "experiment_summary": self._experiment_runner.summary(),
            "timestamp": time.time(),
        }
        path = self._results_dir / "run_summary.json"
        path.write_text(
            json.dumps(summary, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Run summary saved to %s", path)


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """Command-line interface for running benchmark evaluations."""
    parser = argparse.ArgumentParser(
        description="ChessAdapt Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with GPT-4o on first 5 tasks
  python -m evaluation.runner --model gpt-4o --dry-run --max-tasks 5

  # Full evaluation with Claude
  python -m evaluation.runner --model claude-3.7-sonnet

  # Evaluate all models
  python -m evaluation.runner --all-models
        """,
    )
    parser.add_argument(
        "--model", "-m",
        choices=list(MODEL_CONFIGS.keys()),
        help="Model to evaluate",
    )
    parser.add_argument(
        "--all-models", action="store_true",
        help="Evaluate all configured models",
    )
    parser.add_argument(
        "--tasks", "-t",
        default=DEFAULT_TASKS_PATH,
        help="Path to tasks JSONL file",
    )
    parser.add_argument(
        "--max-tasks", type=int, default=None,
        help="Limit number of tasks (for testing)",
    )
    parser.add_argument(
        "--results-dir", default=DEFAULT_RESULTS_DIR,
        help="Output directory for results",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="No API calls — test prompt construction only",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    )

    if args.all_models:
        models = list(MODEL_CONFIGS.keys())
    elif args.model:
        models = [args.model]
    else:
        parser.error("Specify --model or --all-models")
        return

    for model_key in models:
        print(f"\n{'='*60}")
        print(f"  Evaluating: {MODEL_CONFIGS[model_key].name}")
        print(f"{'='*60}\n")

        runner = BenchmarkRunner(
            model_key=model_key,
            results_dir=args.results_dir,
            dry_run=args.dry_run,
        )
        runner.run(
            tasks_path=args.tasks,
            max_tasks=args.max_tasks,
        )

        summary = runner.summary()
        print(f"\n--- {MODEL_CONFIGS[model_key].name} Summary ---")
        print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
