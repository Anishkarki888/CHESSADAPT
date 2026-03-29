# pipeline/serializer.py
# Validates and writes TaskItem dicts to JSONL files.
# Called by pairer.py — can also be used standalone to re-serialize
# or re-validate an existing task file.
#
# Run directly to validate an existing task file:
#   python -m pipeline.serializer --file data/tasks/t1_tasks.jsonl

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tasks.schemas import TaskItem

REQUIRED_FIELDS = {
    "fen",
    "rule_delta",
    "prompt_template",
    "legal_moves",
    "difficulty_tier",
    "task_type",
    "source_game_id",
}

VALID_TASK_TYPES  = {"T1", "T2", "T3"}
VALID_DIFFICULTY  = {"easy", "medium", "hard"}


def validate_item(item: dict, line_no: int) -> list[str]:
    """
    Validate one task item dict. Returns a list of error strings
    (empty list means the item is valid).
    """
    errors = []

    # Required fields present
    missing = REQUIRED_FIELDS - set(item.keys())
    if missing:
        errors.append(f"Line {line_no}: missing fields {missing}")
        return errors  # can't validate further without required fields

    # task_type
    if item["task_type"] not in VALID_TASK_TYPES:
        errors.append(f"Line {line_no}: invalid task_type '{item['task_type']}'")

    # difficulty_tier
    if item["difficulty_tier"] not in VALID_DIFFICULTY:
        errors.append(f"Line {line_no}: invalid difficulty_tier '{item['difficulty_tier']}'")

    # legal_moves must be a non-empty list of strings
    lm = item.get("legal_moves", [])
    if not isinstance(lm, list) or len(lm) == 0:
        errors.append(f"Line {line_no}: legal_moves is empty or not a list")
    elif not all(isinstance(m, str) for m in lm):
        errors.append(f"Line {line_no}: legal_moves contains non-string entries")

    # FEN must have 6 space-separated parts
    fen_parts = item.get("fen", "").split()
    if len(fen_parts) != 6:
        errors.append(f"Line {line_no}: fen does not have 6 fields: '{item['fen']}'")

    # rule_delta must have required sub-fields
    rd = item.get("rule_delta", {})
    for sub in ("type", "perturbation", "description"):
        if sub not in rd:
            errors.append(f"Line {line_no}: rule_delta missing '{sub}'")

    return errors


def write_jsonl(items: list[dict | TaskItem], path: str) -> None:
    """
    Validate then write a list of task items to a JSONL file.
    Raises ValueError if any items fail validation.
    """
    out    = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    dicts  = [asdict(i) if isinstance(i, TaskItem) else i for i in items]
    errors = []

    for i, item in enumerate(dicts, start=1):
        errors.extend(validate_item(item, i))

    if errors:
        err_str = "\n".join(errors[:20])  # cap output at 20 errors
        extra   = len(errors) - 20
        if extra > 0:
            err_str += f"\n... and {extra} more errors"
        raise ValueError(f"Validation failed:\n{err_str}")

    with out.open("w", encoding="utf-8") as f:
        for item in dicts:
            f.write(json.dumps(item) + "\n")

    print(f"Serialized {len(dicts):,} valid items → {out.resolve()}")


def read_jsonl(path: str) -> list[dict]:
    """Read and validate an existing JSONL task file. Returns list of dicts."""
    items  = []
    errors = []

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {i}: JSON parse error — {e}")
                continue
            errors.extend(validate_item(item, i))
            items.append(item)

    if errors:
        for err in errors[:20]:
            print(f"  WARN: {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors)-20} more warnings")

    print(f"Read {len(items):,} items from {path}  ({len(errors)} warnings)")
    return items


def print_sample(path: str, n: int = 3) -> None:
    """Pretty-print the first N items from a JSONL task file."""
    items = read_jsonl(path)
    for item in items[:n]:
        print(json.dumps(item, indent=2))
        print("─" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a JSONL task file.")
    parser.add_argument("--file", required=True, help="Path to a task JSONL file")
    parser.add_argument("--sample", type=int, default=0,
                        help="Print N sample items (default: 0)")
    args = parser.parse_args()

    items = read_jsonl(args.file)
    if args.sample > 0:
        print_sample(args.file, n=args.sample)
