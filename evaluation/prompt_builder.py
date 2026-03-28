"""
Prompt construction for ChessAdapt benchmark tasks.

Builds structured natural-language prompts from a FEN position and a
rule-delta specification.  Three templates cover T1 (single move),
T2 (best move), and T3 (3-move sequence with stacked rules).
"""

from __future__ import annotations

import chess


# ── Piece display helpers ────────────────────────────────────────────────────

_PIECE_NAMES = {
    chess.PAWN: "Pawn", chess.KNIGHT: "Knight", chess.BISHOP: "Bishop",
    chess.ROOK: "Rook", chess.QUEEN: "Queen", chess.KING: "King",
}


def _board_ascii(fen: str) -> str:
    """Return a human-readable board diagram from a FEN string."""
    return str(chess.Board(fen))


def _turn_label(fen: str) -> str:
    board = chess.Board(fen)
    return "White" if board.turn else "Black"


# ── Rule-delta → natural language ────────────────────────────────────────────

_RULE_DESCRIPTIONS: dict[str, str] = {
    "bishop_as_rook": (
        "Bishops now move like Rooks — they slide along ranks and files "
        "(orthogonally) instead of diagonally."
    ),
    "knight_two_squares": (
        "Knights now move exactly 2 squares in any direction (horizontal, "
        "vertical, or diagonal) instead of the standard L-shape."
    ),
    "queen_no_backwards": (
        "The Queen cannot move backwards (toward its own first rank). "
        "It may only move forward or sideways."
    ),
    "pawn_forward_capture": (
        "Pawns now capture by moving straight forward (not diagonally). "
        "A Pawn captures an enemy piece directly in front of it."
    ),
    "capture_all_pawns": (
        "The win condition has changed: you win by capturing ALL of your "
        "opponent's Pawns. Checkmate is disabled."
    ),
    "centre_race": (
        "The win condition has changed: the first player to move a piece "
        "to e4 (White) or e5 (Black) wins immediately."
    ),
    "two_moves_per_turn": (
        "Each player makes TWO moves per turn instead of one. After your "
        "first move, you move again before your opponent responds."
    ),
    "no_repeat_piece": (
        "You cannot move the same piece that was just moved on the "
        "previous turn. Choose a different piece."
    ),
}


def _describe_rule(rule_name: str) -> str:
    """Return a natural-language description for a rule perturbation."""
    return _RULE_DESCRIPTIONS.get(
        rule_name,
        f"A custom rule change called '{rule_name}' is in effect.",
    )


# ── Prompt templates ─────────────────────────────────────────────────────────

_T1_TEMPLATE = """You are playing a chess variant with a MODIFIED rule.

## Position (FEN)
```
{fen}
```

## Board
```
{board}
```

It is {turn}'s turn to move.

## Rule Change
{rule_description}

## Task
Given this position and the rule change above, provide exactly ONE legal move in UCI format (e.g., "e2e4", "g1f3").

IMPORTANT:
- The move MUST be legal under the MODIFIED rule, not standard chess.
- Think step-by-step about how the rule change affects which moves are legal.
- Respond with ONLY the move in UCI format, nothing else.

Your move:"""

_T2_TEMPLATE = """You are playing a chess variant with a MODIFIED rule.

## Position (FEN)
```
{fen}
```

## Board
```
{board}
```

It is {turn}'s turn to move.

## Rule Change
{rule_description}

## Task
Given this position and the rule change above, provide the BEST strategic move in UCI format.

IMPORTANT:
- The move MUST be legal under the MODIFIED rule, not standard chess.
- Consider both the rule change AND strategic quality.
- Think step-by-step about what constitutes a strong move under the new rules.
- Respond with ONLY the move in UCI format (e.g., "e2e4"), nothing else.

Your best move:"""

_T3_TEMPLATE = """You are playing a chess variant with MULTIPLE modified rules active simultaneously.

## Position (FEN)
```
{fen}
```

## Board
```
{board}
```

It is {turn}'s turn to move.

## Active Rule Changes
{rule_descriptions}

## Task
Given this position and ALL the rule changes above, provide a sequence of exactly 3 legal moves in UCI format.

IMPORTANT:
- ALL moves must be legal under ALL modified rules simultaneously.
- Think carefully about how the rules interact with each other.
- Consider the cumulative effect on the position after each move.
- Respond with exactly 3 moves, one per line, in UCI format.

Your 3-move sequence:"""


# ── PromptBuilder ────────────────────────────────────────────────────────────

class PromptBuilder:
    """
    Constructs evaluation prompts from task items.

    Usage::

        builder = PromptBuilder()
        prompt = builder.build(
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            rule_names=["bishop_as_rook"],
            task_type="T1",
        )
    """

    @staticmethod
    def build(
        fen: str,
        rule_names: list[str],
        task_type: str = "T1",
    ) -> str:
        """
        Build a formatted prompt for the given task.

        Parameters
        ----------
        fen : str
            FEN string of the board position.
        rule_names : list[str]
            Active perturbation rule names.
        task_type : str
            One of "T1", "T2", "T3".

        Returns
        -------
        str
            The complete prompt to send to the LLM.
        """
        board = _board_ascii(fen)
        turn = _turn_label(fen)

        if task_type == "T1":
            rule_desc = _describe_rule(rule_names[0])
            return _T1_TEMPLATE.format(
                fen=fen, board=board, turn=turn, rule_description=rule_desc,
            )

        elif task_type == "T2":
            rule_desc = _describe_rule(rule_names[0])
            return _T2_TEMPLATE.format(
                fen=fen, board=board, turn=turn, rule_description=rule_desc,
            )

        elif task_type == "T3":
            descriptions = "\n".join(
                f"{i+1}. **{name}**: {_describe_rule(name)}"
                for i, name in enumerate(rule_names)
            )
            return _T3_TEMPLATE.format(
                fen=fen, board=board, turn=turn, rule_descriptions=descriptions,
            )

        else:
            raise ValueError(f"Unknown task_type: {task_type!r}")

    @staticmethod
    def describe_rule(rule_name: str) -> str:
        """Return the natural-language description for a rule."""
        return _describe_rule(rule_name)
