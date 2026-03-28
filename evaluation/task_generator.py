"""
Generate benchmark task items from positions.jsonl.

Creates T1, T2, and T3 task instances by pairing real middlegame
positions with perturbation rules from the engine registry.
"""

from __future__ import annotations

import itertools
import json
import logging
import random
from pathlib import Path
from typing import Any

from engine.registry import REGISTRY
from engine.composition.composer import RuleComposer
from evaluation.prompt_builder import PromptBuilder

logger = logging.getLogger("chessadapt.task_generator")

# ── Perturbation pools by category ───────────────────────────────────────────

_MOVEMENT_RULES = [
    "bishop_as_rook", "knight_two_squares",
    "queen_no_backwards", "pawn_forward_capture",
]
_WIN_RULES = ["capture_all_pawns", "centre_race"]
_TURN_RULES = ["two_moves_per_turn", "no_repeat_piece"]

_ALL_RULES = _MOVEMENT_RULES + _WIN_RULES + _TURN_RULES

# Difficulty assignment: rule → difficulty
_RULE_DIFFICULTY: dict[str, str] = {}
for rule_name, cls in REGISTRY.items():
    _RULE_DIFFICULTY[rule_name] = cls.difficulty


# ── Task item schema ─────────────────────────────────────────────────────────

def _build_task_item(
    fen: str,
    rule_names: list[str],
    task_type: str,
    source_game_id: str = "",
    move_number: int = 0,
) -> dict[str, Any]:
    """
    Build a single benchmark task item.

    Returns a dict with: fen, rule_names, rule_delta, prompt,
    legal_moves, difficulty_tier, task_type, source_game_id.
    """
    try:
        composer = RuleComposer(fen, rule_names)
        legal_moves = composer.legal_uci_moves()
        rule_delta = composer.rule_delta()
    except Exception as exc:
        logger.warning(
            "Skipping task (fen=%s, rules=%s): %s", fen, rule_names, exc
        )
        return {}

    if not legal_moves:
        logger.debug("No legal moves for fen=%s rules=%s", fen, rule_names)
        return {}

    prompt = PromptBuilder.build(fen, rule_names, task_type)

    return {
        "fen": fen,
        "rule_names": rule_names,
        "rule_delta": rule_delta,
        "prompt": prompt,
        "legal_moves": legal_moves,
        "difficulty_tier": rule_delta.get("combined_difficulty", "medium"),
        "task_type": task_type,
        "source_game_id": source_game_id,
        "move_number": move_number,
    }


# ── TaskGenerator ────────────────────────────────────────────────────────────

class TaskGenerator:
    """
    Generate benchmark tasks from a positions JSONL file.

    Usage::

        gen = TaskGenerator("data/positions/positions.jsonl")
        tasks = gen.generate_all(t1_count=200, t2_count=200, t3_count=100)
        gen.save(tasks, "data/tasks/tasks.jsonl")
    """

    def __init__(self, positions_path: str | Path) -> None:
        self._positions_path = Path(positions_path)
        self._positions = self._load_positions()
        logger.info("Loaded %d positions from %s", len(self._positions), self._positions_path)

    def _load_positions(self) -> list[dict]:
        """Load positions from JSONL file."""
        positions = []
        with open(self._positions_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    positions.append(json.loads(line))
        return positions

    def generate_t1(self, count: int = 200, seed: int = 42) -> list[dict]:
        """
        Generate T1 tasks: single rule, one move.

        Each position is paired with a randomly selected single rule.
        """
        rng = random.Random(seed)
        tasks = []

        positions = list(self._positions)
        rng.shuffle(positions)

        for pos in itertools.islice(itertools.cycle(positions), count):
            rule = rng.choice(_ALL_RULES)
            task = _build_task_item(
                fen=pos["fen"],
                rule_names=[rule],
                task_type="T1",
                source_game_id=pos.get("source_game_id", ""),
                move_number=pos.get("move_number", 0),
            )
            if task:
                tasks.append(task)

        logger.info("Generated %d T1 tasks", len(tasks))
        return tasks

    def generate_t2(self, count: int = 200, seed: int = 43) -> list[dict]:
        """
        Generate T2 tasks: single rule, best move.

        Same as T1 but scored for strategic quality.
        """
        rng = random.Random(seed)
        tasks = []

        positions = list(self._positions)
        rng.shuffle(positions)

        for pos in itertools.islice(itertools.cycle(positions), count):
            rule = rng.choice(_ALL_RULES)
            task = _build_task_item(
                fen=pos["fen"],
                rule_names=[rule],
                task_type="T2",
                source_game_id=pos.get("source_game_id", ""),
                move_number=pos.get("move_number", 0),
            )
            if task:
                tasks.append(task)

        logger.info("Generated %d T2 tasks", len(tasks))
        return tasks

    def generate_t3(self, count: int = 100, seed: int = 44) -> list[dict]:
        """
        Generate T3 tasks: stacked rules, 3-move sequence.

        Each position gets 2–3 rules from different categories to
        maximize cognitive load.
        """
        rng = random.Random(seed)
        tasks = []

        positions = list(self._positions)
        rng.shuffle(positions)

        # Generate cross-category rule combos
        combos_2 = [
            [m, t]
            for m in _MOVEMENT_RULES
            for t in _TURN_RULES
        ]
        combos_3 = [
            [m, w, t]
            for m in _MOVEMENT_RULES
            for w in _WIN_RULES
            for t in _TURN_RULES
        ]
        all_combos = combos_2 + combos_3

        for pos in itertools.islice(itertools.cycle(positions), count):
            rules = rng.choice(all_combos)
            task = _build_task_item(
                fen=pos["fen"],
                rule_names=rules,
                task_type="T3",
                source_game_id=pos.get("source_game_id", ""),
                move_number=pos.get("move_number", 0),
            )
            if task:
                tasks.append(task)

        logger.info("Generated %d T3 tasks", len(tasks))
        return tasks

    def generate_all(
        self,
        t1_count: int = 200,
        t2_count: int = 200,
        t3_count: int = 100,
    ) -> list[dict]:
        """Generate all task types and return combined list."""
        tasks = []
        tasks.extend(self.generate_t1(t1_count))
        tasks.extend(self.generate_t2(t2_count))
        tasks.extend(self.generate_t3(t3_count))
        logger.info("Generated %d total tasks", len(tasks))
        return tasks

    @staticmethod
    def save(tasks: list[dict], output_path: str | Path) -> Path:
        """Save tasks to a JSONL file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for task in tasks:
                f.write(json.dumps(task, default=str) + "\n")
        logger.info("Saved %d tasks to %s", len(tasks), path)
        return path

    @staticmethod
    def load(tasks_path: str | Path) -> list[dict]:
        """Load tasks from a JSONL file."""
        tasks = []
        with open(tasks_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tasks.append(json.loads(line))
        return tasks
