"""
RuleComposer — stacks multiple perturbation rules onto a single board.

For T1/T2 tasks a single rule is applied.  For T3 tasks two or three rules
are composed simultaneously:

  • Movement rules → legal-move sets are **intersected** (a move must be
    legal under ALL active movement perturbations).
  • Win conditions → **OR-combined** (any win condition triggers game over).
  • Turn structure → the most restrictive rule is applied.

The composer uses LoggingMixin and StateTrackingMixin so every board
interaction is logged and recorded for downstream scoring.
"""

from __future__ import annotations

import logging
import time
from typing import Sequence

import chess

from engine.base import PerturbedBoard
from engine.registry import REGISTRY
from engine.composition.mixins import LoggingMixin, StateTrackingMixin


class RuleComposer(LoggingMixin, StateTrackingMixin):
    """
    High-level composition engine.

    Parameters
    ----------
    fen : str
        Starting FEN string.
    rule_names : list[str]
        One or more rule names from the REGISTRY.

    Example
    -------
    >>> composer = RuleComposer(chess.STARTING_FEN, ["bishop_as_rook", "no_repeat_piece"])
    >>> print(composer.legal_uci_moves())
    """

    def __init__(self, fen: str, rule_names: list[str]) -> None:
        if not rule_names:
            raise ValueError("At least one rule name is required")

        # Validate all rule names before proceeding
        unknown = [r for r in rule_names if r not in REGISTRY]
        if unknown:
            raise ValueError(f"Unknown rule(s): {unknown}")

        self._fen = fen
        self._rule_names_list = list(rule_names)

        # Create a separate board instance for each rule
        self._boards: dict[str, PerturbedBoard] = {
            name: REGISTRY[name](fen) for name in rule_names
        }

        # Classify boards by category for composition logic
        self._movement_boards: list[PerturbedBoard] = []
        self._win_boards: list[PerturbedBoard] = []
        self._turn_boards: list[PerturbedBoard] = []

        for name, board in self._boards.items():
            cat = board.category
            if cat == "movement":
                self._movement_boards.append(board)
            elif cat == "win_condition":
                self._win_boards.append(board)
            elif cat == "turn_structure":
                self._turn_boards.append(board)

        # Keep a standard board for inhibition comparison
        self._standard_board = chess.Board(fen)

        # A "primary" board for base operations (FEN, turn, piece layout)
        # Use the first board as canonical reference
        self._primary: PerturbedBoard = next(iter(self._boards.values()))

        # Determine the combined category string
        categories = sorted({b.category for b in self._boards.values()})
        self._combined_category = "+".join(categories)

        # Initialise mixins
        self._init_logging(
            name="composer",
            rule_names=self._rule_names_list,
        )
        self._init_state_tracking(
            rule_names=self._rule_names_list,
            category=self._combined_category,
        )

        self._log_info(
            "RuleComposer initialised | fen=%s | rules=%s | categories=%s",
            fen,
            "+".join(self._rule_names_list),
            self._combined_category,
        )

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def fen(self) -> str:
        """Current FEN from the primary board."""
        return self._primary.fen()

    @property
    def turn(self) -> chess.Color:
        return self._primary.turn

    @property
    def rule_names(self) -> list[str]:
        return list(self._rule_names_list)

    # ── Rule delta ───────────────────────────────────────────────────────

    def rule_delta(self) -> dict:
        """
        Combined rule metadata for all active perturbations.
        Suitable for inclusion in a benchmark task item.
        """
        deltas = []
        for name, board in self._boards.items():
            deltas.append(board.rule_delta())

        difficulties = [b.difficulty for b in self._boards.values()]
        # combined difficulty = hardest individual rule
        difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
        combined_difficulty = max(difficulties, key=lambda d: difficulty_order.get(d, 0))

        return {
            "rules": deltas,
            "combined_category": self._combined_category,
            "combined_difficulty": combined_difficulty,
            "rule_count": len(self._boards),
        }

    # ── Legal moves (composed) ───────────────────────────────────────────

    def _compute_legal_moves(self) -> set[chess.Move]:
        """
        Compute the set of legal moves under the composed ruleset.

        Strategy:
          1. Start with the union of all boards' legal moves.
          2. For movement boards: intersect (move must pass ALL).
          3. Turn-structure boards may further filter.
          4. Standard legality is checked by the individual boards already.
        """
        # If there is only one board, just use its legal moves directly
        if len(self._boards) == 1:
            return set(self._primary.legal_moves)

        # Start with all legal moves from each individual board
        per_board_moves: dict[str, set[chess.Move]] = {}
        for name, board in self._boards.items():
            per_board_moves[name] = set(board.legal_moves)

        # Movement rules: intersect — a move is legal only if ALL movement
        # boards agree it is legal
        if self._movement_boards:
            movement_sets = [
                per_board_moves[b.rule_name] for b in self._movement_boards
            ]
            movement_legal = set.intersection(*movement_sets)
        else:
            movement_legal = None

        # Turn-structure rules: intersect — most restrictive wins
        if self._turn_boards:
            turn_sets = [
                per_board_moves[b.rule_name] for b in self._turn_boards
            ]
            turn_legal = set.intersection(*turn_sets)
        else:
            turn_legal = None

        # Combine: start with union of all board moves, then restrict
        # by movement and turn intersections
        all_moves = set()
        for moves in per_board_moves.values():
            all_moves |= moves

        if movement_legal is not None:
            all_moves &= movement_legal

        if turn_legal is not None:
            all_moves &= turn_legal

        return all_moves

    @property
    def legal_moves(self) -> set[chess.Move]:
        return self._compute_legal_moves()

    def legal_uci_moves(self) -> list[str]:
        """Return legal moves as sorted UCI strings."""
        return sorted(m.uci() for m in self._compute_legal_moves())

    # ── Move validation ──────────────────────────────────────────────────

    def validate_move(self, uci: str, **extra: Any) -> dict:
        """
        Check a single move against the composed ruleset AND standard chess.
        """
        t0 = time.perf_counter()

        move = chess.Move.from_uci(uci)
        legal_composed = move in self._compute_legal_moves()

        # Standard chess check for inhibition scoring
        std_board = chess.Board(self.fen)
        legal_standard = move in std_board.legal_moves

        is_inhibition_failure = legal_standard and not legal_composed

        elapsed_ms = (time.perf_counter() - t0) * 1000

        fen_before = self.fen

        # Record event
        self._record_event(
            fen_before=fen_before,
            fen_after=fen_before,  # no push happened
            move_uci=uci,
            is_legal_perturbed=legal_composed,
            is_legal_standard=legal_standard,
            elapsed_ms=elapsed_ms,
            **extra,
        )

        # Log
        level = logging.INFO if legal_composed else logging.WARNING
        self._log_move(
            level,
            uci,
            fen_before,
            legal_composed,
            f"inhibition_fail={is_inhibition_failure}",
        )

        return {
            "legal": legal_composed,
            "is_old_rule": legal_standard,
            "uci_move": uci,
            "is_inhibition_failure": is_inhibition_failure,
        }

    def push(self, uci: str, **extra: Any) -> dict:
        """
        Apply a move to ALL internal boards.
        """
        t0 = time.perf_counter()
        move = chess.Move.from_uci(uci)

        legal_set = self._compute_legal_moves()
        is_legal = move in legal_set

        std_board = chess.Board(self.fen)
        is_legal_standard = move in std_board.legal_moves

        fen_before = self.fen

        if not is_legal:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._record_event(
                fen_before=fen_before,
                fen_after=fen_before,
                move_uci=uci,
                is_legal_perturbed=False,
                is_legal_standard=is_legal_standard,
                elapsed_ms=elapsed_ms,
                **extra,
            )
            self._log_move(
                logging.ERROR, uci, fen_before, False, "REJECTED"
            )
            raise ValueError(
                f"Illegal move {uci} under composed rules "
                f"{self._rule_names_list}"
            )

        # Push to ALL boards
        for board in self._boards.values():
            board.push(move)
        self._standard_board.push(move)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        fen_after = self.fen

        self._record_event(
            fen_before=fen_before,
            fen_after=fen_after,
            move_uci=uci,
            is_legal_perturbed=True,
            is_legal_standard=is_legal_standard,
            elapsed_ms=elapsed_ms,
            **extra,
        )
        self._log_move(logging.INFO, uci, fen_before, True, "PUSHED")

        return {
            "legal": True,
            "is_old_rule": is_legal_standard,
            "uci_move": uci,
            "fen_after": fen_after,
        }

    def pop(self) -> chess.Move:
        """Undo the last move on ALL internal boards."""
        moves = []
        for board in self._boards.values():
            moves.append(board.pop())
        self._standard_board.pop()

        self._log_debug("POP | fen=%s", self.fen)
        return moves[0]  # all boards should agree

    # ── Win condition (composed) ─────────────────────────────────────────

    def is_game_over(self) -> bool:
        """Game is over if ANY win-condition board says so."""
        if self._win_boards:
            return any(b.is_game_over() for b in self._win_boards)
        # fall back to standard game-over from primary board
        return self._primary.is_game_over()

    def outcome(self) -> chess.Outcome | None:
        """Return the outcome from the first triggered win condition."""
        for board in self._win_boards:
            o = board.outcome()
            if o is not None:
                return o
        if not self._win_boards:
            return self._primary.outcome()
        return None

    # ── Display helpers ──────────────────────────────────────────────────

    def __str__(self) -> str:
        rules = " + ".join(self._rule_names_list)
        return f"[RuleComposer: {rules}]\n{self._primary}"

    def __repr__(self) -> str:
        return (
            f"RuleComposer(fen={self._fen!r}, "
            f"rules={self._rule_names_list!r})"
        )
