"""
pipeline/run_metacognition.py

ChessAdapt Metacognition Benchmark — Task Generator.

Generates T1/T2/T3 tasks with self-reflection and confidence fields.
Hard-tier T1 items use predict_first mode to measure prospective metacognition.
"""

import argparse
import json
from pathlib import Path

from tqdm import tqdm

from engine.legal_moves import get_legal_moves_cached
from pipeline.difficulty import DifficultyClassifier
from pipeline.prompt_builder_metacognition import build_metacognition_prompt
from tasks.schemas import TaskItem


POSITIONS_PATH = "data/positions/positions.jsonl"
TASKS_DIR      = "data/tasks_metacognition"

RULE_DESCRIPTIONS = {
    "bishop_as_rook":       "Bishops move orthogonally only — horizontally or vertically any number of squares. Diagonal movement is illegal.",
    "knight_two_squares":   "Knights move exactly 2 squares in any direction — horizontally, vertically, or diagonally. The standard L-shape is illegal.",
    "queen_no_backwards":   "The queen cannot move toward its own back rank. Only forward and sideways movement is allowed.",
    "pawn_forward_capture": "Pawns capture directly forward instead of diagonally. Diagonal pawn captures are illegal.",
    "capture_all_pawns":    "The first player to capture all opponent pawns wins, regardless of check or checkmate.",
    "centre_race":          "The first player to move any piece onto e4 or e5 wins immediately.",
    "two_moves_per_turn":   "Each player makes exactly two consecutive moves per turn before the opponent replies.",
    "no_repeat_piece":      "A player cannot move the same piece that was moved on their previous turn.",
}

RULE_GEOMETRIC_DESCRIPTIONS = {
    "bishop_as_rook":       "One piece type may only travel in straight lines — left, right, forward, or backward — any number of empty squares. It cannot travel diagonally under any circumstance.",
    "knight_two_squares":   "One piece type may move exactly 2 squares in any direction — horizontally, vertically, or diagonally. No other distance or path is permitted.",
    "queen_no_backwards":   "One piece type may not move in the direction of its own starting rank. It may only move laterally or away from its starting rank.",
    "pawn_forward_capture": "One piece type captures by moving directly forward into the target square, not at an angle.",
    "capture_all_pawns":    "Victory is achieved by removing all of the opponent's smallest pieces from the board.",
    "centre_race":          "Victory is achieved by placing any piece on one of the two central squares of the board.",
    "two_moves_per_turn":   "Each side executes two actions before control passes to the opponent.",
    "no_repeat_piece":      "The piece moved on the current turn must differ from the piece moved on the immediately preceding turn.",
}

T3_STACKED_COMBOS = [
    ("bishop_as_rook",       "two_moves_per_turn"),
    ("knight_two_squares",   "no_repeat_piece"),
    ("queen_no_backwards",   "capture_all_pawns"),
    ("pawn_forward_capture", "two_moves_per_turn"),
]

T3_TOP_N_HARD = 100


def _build_rule_delta(primary: str, stacked: str | None = None) -> dict:
    """
    Build a rule_delta dict with human-readable descriptions
    for both Variant A (named) and Variant B (geometric).
    """
    delta = {
        "perturbation":          primary,
        "type":                  "metacognition",
        "description":           RULE_DESCRIPTIONS[primary],
        "geometric_description": RULE_GEOMETRIC_DESCRIPTIONS[primary],
    }
    if stacked:
        delta["stacked_description"]            = RULE_DESCRIPTIONS[stacked]
        delta["stacked_geometric_description"]  = RULE_GEOMETRIC_DESCRIPTIONS[stacked]
        delta["stacked_perturbation"]           = stacked
    return delta


def main():
    parser = argparse.ArgumentParser(description="ChessAdapt Metacognition Task Generator")
    parser.add_argument("--positions", default=POSITIONS_PATH)
    parser.add_argument("--tasks-dir", default=TASKS_DIR)
    parser.add_argument("--sample", type=int, default=None,
                        help="Limit to first N positions (for smoke testing)")
    args = parser.parse_args()

    out = Path(args.tasks_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("\nChessAdapt — Metacognition Pipeline")
    print("=" * 50)

    positions = []
    with open(args.positions, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                positions.append(json.loads(line))

    if args.sample:
        positions = positions[: args.sample]
        print(f"Smoke test mode: using {args.sample} positions")

    t1_items, t2_items, t3_items = [], [], []

    all_perturbations = list(RULE_DESCRIPTIONS.keys())

    with DifficultyClassifier() as dc:

        for pos in tqdm(positions, desc="Building T1 / T2"):
            fen = pos["fen"]
            gid = pos["source_game_id"]

            for pert in all_perturbations:
                try:
                    moves = list(get_legal_moves_cached(fen, pert))
                    if not moves:
                        continue

                    diff       = dc.classify(fen, pert)
                    rule_delta = _build_rule_delta(pert)

                    t1_items.append(TaskItem(
                        fen=fen,
                        rule_delta=rule_delta,
                        prompt_template=build_metacognition_prompt(
                            fen, rule_delta, "T1",
                            predict_first=(diff == "hard"),
                        ),
                        legal_moves=moves,
                        difficulty_tier=diff,
                        task_type="T1",
                        source_game_id=gid,
                    ))

                    t2_items.append(TaskItem(
                        fen=fen,
                        rule_delta=rule_delta,
                        prompt_template=build_metacognition_prompt(
                            fen, rule_delta, "T2",
                        ),
                        legal_moves=moves,
                        difficulty_tier=diff,
                        task_type="T2",
                        source_game_id=gid,
                    ))

                except Exception:
                    continue

        for pos in tqdm(positions[:T3_TOP_N_HARD], desc="Building T3"):
            fen = pos["fen"]
            gid = pos["source_game_id"]

            for p1, p2 in T3_STACKED_COMBOS:
                try:
                    l1    = set(get_legal_moves_cached(fen, p1))
                    l2    = set(get_legal_moves_cached(fen, p2))
                    moves = list(l1 & l2)
                    if not moves:
                        continue

                    rule_delta = _build_rule_delta(p1, stacked=p2)

                    t3_items.append(TaskItem(
                        fen=fen,
                        rule_delta=rule_delta,
                        prompt_template=build_metacognition_prompt(
                            fen, rule_delta, "T3",
                        ),
                        legal_moves=moves,
                        difficulty_tier="hard",
                        task_type="T3",
                        source_game_id=gid,
                    ))

                except Exception:
                    continue

    for fname, items in [
        ("t1_tasks.jsonl", t1_items),
        ("t2_tasks.jsonl", t2_items),
        ("t3_tasks.jsonl", t3_items),
    ]:
        with (out / fname).open("w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item.__dict__) + "\n")

        print(f"  {fname}: {len(items)} tasks")

    print(f"\nDone. Tasks saved to: {out.resolve()}")


if __name__ == "__main__":
    main()