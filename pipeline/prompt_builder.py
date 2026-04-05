# pipeline/prompt_builder.py
# Builds the natural language prompt delivered to the model under test.
# Supports two variants:
#   Variant A — named rule description (standard)
#   Variant B — geometric description only, no piece names (Chinese Room test)
# Each task type gets a distinct template — T3 explicitly requests a sequence.

from typing import Literal

TaskType = Literal["T1", "T2", "T3"]
Variant = Literal["A", "B"]

# ── Variant A Templates (Named Rule) ────────────────────────────────────────

_T1_TEMPLATE_A = """\
You are playing chess with one modified rule:
{rule_description}

Current position (FEN): {fen}
It is {side} to move.

Provide exactly one legal move in UCI notation (e.g. e2e4, g1f3).
Output only the move, nothing else.\
"""

_T2_TEMPLATE_A = """\
You are playing chess with one modified rule:
{rule_description}

Current position (FEN): {fen}
It is {side} to move.

Find the best move under this rule. Provide your answer in UCI notation (e.g. e2e4).
Output only the move, nothing else.\
"""

_T3_TEMPLATE_A = """\
You are playing chess with these modified rules:
{rule_list}

Current position (FEN): {fen}
It is {side} to move.

Provide a sequence of exactly 3 moves in UCI notation, one per line.
Apply all modified rules consistently across every move.
Output only the 3 moves, one per line, nothing else.\
"""

# ── Variant B Templates (Geometric — Chinese Room) ───────────────────────────
# IMPORTANT: Variant B descriptions must NEVER mention piece names.
# The rule is described only in terms of geometry (squares, directions, distance).

_T1_TEMPLATE_B = """\
You are playing chess with one modified rule applying to a specific piece type:
{geometric_description}

Current position (FEN): {fen}
It is {side} to move.

Provide exactly one legal move in UCI notation (e.g. e2e4, g1f3).
Output only the move, nothing else.\
"""

_T2_TEMPLATE_B = """\
You are playing chess with one modified rule applying to a specific piece type:
{geometric_description}

Current position (FEN): {fen}
It is {side} to move.

Find the best move under this rule. Provide your answer in UCI notation (e.g. e2e4).
Output only the move, nothing else.\
"""

_T3_TEMPLATE_B = """\
You are playing chess with these modified rules applying to specific piece types:
{geometric_rule_list}

Current position (FEN): {fen}
It is {side} to move.

Provide a sequence of exactly 3 moves in UCI notation, one per line.
Apply all modified rules consistently across every move.
Output only the 3 moves, one per line, nothing else.\
"""


def _side_to_move(fen: str) -> str:
    """Parse the active color from a FEN string."""
    parts = fen.split()
    if len(parts) >= 2:
        return "White" if parts[1] == "w" else "Black"
    return "White"


def build_prompt(
    fen: str,
    rule_delta: dict,
    task_type: TaskType,
    variant: Variant = "A",
) -> str:
    """
    Build the prompt string for a task item.

    Args:
        fen:        Position FEN string.
        rule_delta: The rule_delta dict from the TaskItem.
                    Variant A uses rule_delta["description"].
                    Variant B uses rule_delta["geometric_description"].
        task_type:  "T1", "T2", or "T3".
        variant:    "A" = named rule (standard).
                    "B" = geometric description only (Chinese Room test).

    Returns:
        Fully formatted prompt string ready to send to the model.
    """
    side = _side_to_move(fen)

    # ── Variant B (Geometric / Chinese Room) ────────────────────────────────
    if variant == "B":
        geo_desc = rule_delta.get("geometric_description", "")

        if task_type == "T3":
            geo_rules = [f"1. {geo_desc}"]
            if "stacked_geometric_description" in rule_delta:
                geo_rules.append(f"2. {rule_delta['stacked_geometric_description']}")
            geometric_rule_list = "\n".join(geo_rules)
            return _T3_TEMPLATE_B.format(
                fen=fen, side=side, geometric_rule_list=geometric_rule_list
            )

        if task_type == "T1":
            return _T1_TEMPLATE_B.format(
                fen=fen, side=side, geometric_description=geo_desc
            )

        # T2
        return _T2_TEMPLATE_B.format(
            fen=fen, side=side, geometric_description=geo_desc
        )

    # ── Variant A (Named / Standard) ────────────────────────────────────────
    if task_type == "T3":
        rules = [f"1. {rule_delta['description']}"]
        if "stacked_description" in rule_delta:
            rules.append(f"2. {rule_delta['stacked_description']}")
        rule_list = "\n".join(rules)
        return _T3_TEMPLATE_A.format(fen=fen, side=side, rule_list=rule_list)

    rule_description = rule_delta["description"]

    if task_type == "T1":
        return _T1_TEMPLATE_A.format(
            fen=fen, side=side, rule_description=rule_description
        )

    # T2
    return _T2_TEMPLATE_A.format(
        fen=fen, side=side, rule_description=rule_description
    )