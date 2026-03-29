# pipeline/prompt_builder.py
# Builds the natural language prompt delivered to the model under test.
# Each task type gets a distinct template — T3 explicitly requests a sequence.

from typing import Literal

TaskType = Literal["T1", "T2", "T3"]


_T1_TEMPLATE = """\
You are playing chess with one modified rule:
{rule_description}

Current position (FEN): {fen}
It is {side} to move.

Provide exactly one legal move in UCI notation (e.g. e2e4, g1f3).
Output only the move, nothing else.\
"""

_T2_TEMPLATE = """\
You are playing chess with one modified rule:
{rule_description}

Current position (FEN): {fen}
It is {side} to move.

Find the best move under this rule. Provide your answer in UCI notation (e.g. e2e4).
Output only the move, nothing else.\
"""

_T3_TEMPLATE = """\
You are playing chess with these modified rules:
{rule_list}

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


def build_prompt(fen: str, rule_delta: dict, task_type: TaskType) -> str:
    """
    Build the prompt string for a task item.

    Args:
        fen:        Position FEN string.
        rule_delta: The rule_delta dict from the TaskItem.
        task_type:  "T1", "T2", or "T3".

    Returns:
        Fully formatted prompt string ready to send to the model.
    """
    side = _side_to_move(fen)

    if task_type == "T3":
        # Build a numbered list of all rules (primary + stacked if present)
        rules = [f"1. {rule_delta['description']}"]
        if "stacked_description" in rule_delta:
            rules.append(f"2. {rule_delta['stacked_description']}")
        rule_list = "\n".join(rules)
        return _T3_TEMPLATE.format(fen=fen, side=side, rule_list=rule_list)

    rule_description = rule_delta["description"]

    if task_type == "T1":
        return _T1_TEMPLATE.format(
            fen=fen, side=side, rule_description=rule_description
        )

    # T2
    return _T2_TEMPLATE.format(
        fen=fen, side=side, rule_description=rule_description
    )
