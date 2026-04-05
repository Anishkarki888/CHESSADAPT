# pipeline/pairer.py
# Cross-products 500 positions × 8 perturbations to produce raw task dicts.
#
# For each (position, perturbation) pair it:
#   1. Precomputes the legal move set under the perturbed rules
#   2. Classifies difficulty (easy / medium / hard)
#   3. Builds the full TaskItem dict ready for the serializer
#
# T3 (stacked rules, 3-move sequence) is generated from the top-N hardest
# positions by pairing them with two-perturbation combos.
#
# Run directly:
#   python -m pipeline.pairer
#   python -m pipeline.pairer --positions data/positions/positions.jsonl

import argparse
import itertools
import json
from pathlib import Path
from typing import Iterator

from tqdm import tqdm

from engine.legal_moves import get_legal_moves_cached
from pipeline.difficulty import DifficultyClassifier
from pipeline.prompt_builder import build_prompt
from tasks.schemas import TaskItem

# ── CONFIG ──────────────────────────────────────────────────────────────
POSITIONS_PATH = "data/positions/positions.jsonl"
TASKS_DIR      = "data/tasks"

# All 8 perturbations from the benchmark spec
ALL_PERTURBATIONS = [
    "bishop_as_rook",
    "knight_two_squares",
    "queen_no_backwards",
    "pawn_forward_capture",
    "capture_all_pawns",
    "centre_race",
    "two_moves_per_turn",
    "no_repeat_piece",
]

# Stacked rule combos for T3 — pairs of perturbations applied simultaneously
T3_STACKED_COMBOS = [
    ("bishop_as_rook",      "two_moves_per_turn"),
    ("knight_two_squares",  "no_repeat_piece"),
    ("queen_no_backwards",  "capture_all_pawns"),
    ("pawn_forward_capture","two_moves_per_turn"),
]

# How many of the hardest positions to use for T3
T3_TOP_N_HARD = 100
# ────────────────────────────────────────────────────────────────────────


def load_positions(path: str) -> list[dict]:
    """Load positions from JSONL — one dict per line."""
    positions = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                positions.append(json.loads(line))
    print(f"Loaded {len(positions)} positions from {path}")
    return positions


# Descriptions for Variant A (Standard)
DESCRIPTIONS = {
    "bishop_as_rook":       ("piece_movement",  "Bishops move orthogonally only, not diagonally"),
    "knight_two_squares":   ("piece_movement",  "Knights move exactly 2 squares in any direction, no L-shape"),
    "queen_no_backwards":   ("piece_movement",  "Queen cannot move towards its own back rank"),
    "pawn_forward_capture": ("piece_movement",  "Pawns capture straight forward, not diagonally"),
    "capture_all_pawns":    ("win_condition",   "Capture all opponent pawns to win instead of checkmate"),
    "centre_race":          ("win_condition",   "First player to move a piece to e4 or e5 wins"),
    "two_moves_per_turn":   ("turn_structure",  "Each player makes two moves per turn"),
    "no_repeat_piece":      ("turn_structure",  "You cannot move the same piece twice in a row"),
}

# Descriptions for Variant B (Geometric / Chinese Room)
GEOMETRIC_DESCRIPTIONS = {
    "bishop_as_rook":       "One piece type may only travel in straight lines — left, right, forward, or backward — any number of empty squares. It cannot travel diagonally under any circumstance.",
    "knight_two_squares":   "One piece type may move exactly 2 squares in any direction — horizontally, vertically, or diagonally. No other distance or path is permitted.",
    "queen_no_backwards":   "One piece type may not move in the direction of its own starting rank. It may only move laterally or away from its starting rank.",
    "pawn_forward_capture": "One piece type captures by moving directly forward into the target square, not at an angle.",
    "capture_all_pawns":    "Victory is achieved by removing all of the opponent's smallest pieces from the board.",
    "centre_race":          "Victory is achieved by placing any piece on one of the two central squares of the board.",
    "two_moves_per_turn":   "Each side executes two actions before control passes to the opponent.",
    "no_repeat_piece":      "The piece moved on the current turn must differ from the piece moved on the immediately preceding turn.",
}


def build_rule_delta(perturbation: str, stacked: str | None = None) -> dict:
    """
    Build the rule_delta field describing the perturbation(s) applied.
    For T3, `stacked` is the second perturbation key.
    """
    cat, desc = DESCRIPTIONS[perturbation]
    geo_desc  = GEOMETRIC_DESCRIPTIONS[perturbation]

    delta = {
        "type":                  cat,
        "perturbation":          perturbation,
        "description":           desc,
        "geometric_description": geo_desc,
    }

    if stacked:
        _, stacked_desc = DESCRIPTIONS[stacked]
        stacked_geo     = GEOMETRIC_DESCRIPTIONS[stacked]
        delta["stacked_perturbation"]           = stacked
        delta["stacked_description"]            = stacked_desc
        delta["stacked_geometric_description"]  = stacked_geo

    return delta


def pair_t1_t2(positions: list[dict], dc: DifficultyClassifier) -> Iterator[TaskItem]:
    """
    Generate T1 and T2 task items.
    """
    total = len(positions) * len(ALL_PERTURBATIONS)

    with tqdm(total=total, desc="Building T1/T2 pairs") as pbar:
        for pos in positions:
            fen     = pos["fen"]
            game_id = pos["source_game_id"]

            for pert in ALL_PERTURBATIONS:
                pbar.update(1)

                try:
                    legal_moves = list(get_legal_moves_cached(fen, pert))
                except Exception as e:
                    print(f"  SKIP {game_id} + {pert}: {e}")
                    continue

                if not legal_moves:
                    continue

                difficulty  = dc.classify(fen, pert)
                rule_delta  = build_rule_delta(pert)

                # T1 — one move, binary scoring
                yield TaskItem(
                    fen             = fen,
                    rule_delta      = rule_delta,
                    prompt_template = build_prompt(fen, rule_delta, task_type="T1"),
                    legal_moves     = legal_moves,
                    difficulty_tier = difficulty,
                    task_type       = "T1",
                    source_game_id  = game_id,
                )

                # T2 — best move, engine-scored (same pair, richer scoring)
                yield TaskItem(
                    fen             = fen,
                    rule_delta      = rule_delta,
                    prompt_template = build_prompt(fen, rule_delta, task_type="T2"),
                    legal_moves     = legal_moves,
                    difficulty_tier = difficulty,
                    task_type       = "T2",
                    source_game_id  = game_id,
                )


def pair_t3(positions: list[dict], dc: DifficultyClassifier) -> Iterator[TaskItem]:
    """
    Generate T3 task items: stacked rules, 3-move sequence.
    """
    # Score each position by how many 'hard' single-rule pairs it produces
    print("Identifying hardest positions for T3...")
    position_hardness: dict[str, int] = {}

    for pos in tqdm(positions, desc="Scoring positions for T3"):
        fen   = pos["fen"]
        count = 0
        for pert in ALL_PERTURBATIONS:
            try:
                if dc.classify(fen, pert) == "hard":
                    count += 1
            except Exception:
                pass
        position_hardness[fen] = count

    # Sort by hardness descending, take top N
    sorted_positions = sorted(
        positions,
        key=lambda p: position_hardness.get(p["fen"], 0),
        reverse=True,
    )
    hard_positions = sorted_positions[:T3_TOP_N_HARD]
    print(f"Selected {len(hard_positions)} hard positions for T3")

    total = len(hard_positions) * len(T3_STACKED_COMBOS)

    with tqdm(total=total, desc="Building T3 stacked pairs") as pbar:
        for pos in hard_positions:
            fen     = pos["fen"]
            game_id = pos["source_game_id"]

            for pert1, pert2 in T3_STACKED_COMBOS:
                pbar.update(1)

                # For stacked rules, legal moves must satisfy BOTH perturbations.
                # Intersection of both legal sets is the conservative safe choice.
                try:
                    legal1 = set(get_legal_moves_cached(fen, pert1))
                    legal2 = set(get_legal_moves_cached(fen, pert2))
                    legal_moves = list(legal1 & legal2)
                except Exception as e:
                    print(f"  SKIP T3 {game_id} + {pert1}/{pert2}: {e}")
                    continue

                if not legal_moves:
                    continue

                rule_delta = build_rule_delta(pert1, stacked=pert2)

                yield TaskItem(
                    fen             = fen,
                    rule_delta      = rule_delta,
                    prompt_template = build_prompt(fen, rule_delta, task_type="T3"),
                    legal_moves     = legal_moves,
                    difficulty_tier = "hard",
                    task_type       = "T3",
                    source_game_id  = game_id,
                )


def run(positions_path: str = POSITIONS_PATH, tasks_dir: str = TASKS_DIR) -> None:
    positions = load_positions(positions_path)
    out       = Path(tasks_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── T1 + T2 ─────────────────────────────────────────────────────────
    t1_items: list[TaskItem] = []
    t2_items: list[TaskItem] = []

    with DifficultyClassifier() as dc:
        for item in pair_t1_t2(positions, dc):
            if item.task_type == "T1":
                t1_items.append(item)
            else:
                t2_items.append(item)

        # ── T3 ───────────────────────────────────────────────────────────────
        t3_items = list(pair_t3(positions, dc))

    # ── Write JSONL ──────────────────────────────────────────────────────
    for filename, items in [
        ("t1_tasks.jsonl", t1_items),
        ("t2_tasks.jsonl", t2_items),
        ("t3_tasks.jsonl", t3_items),
    ]:
        path = out / filename
        with path.open("w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item.__dict__) + "\n")
        print(f"Wrote {len(items):,} items → {path.resolve()}")

    print(f"\nDone. Total task items: {len(t1_items)+len(t2_items)+len(t3_items):,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pair positions with perturbations.")
    parser.add_argument("--positions", default=POSITIONS_PATH)
    parser.add_argument("--tasks-dir", default=TASKS_DIR)
    args = parser.parse_args()
    run(positions_path=args.positions, tasks_dir=args.tasks_dir)
