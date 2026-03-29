# engine/legal_moves.py
# Precomputes legal move sets for a given (FEN, perturbation) pair
# using the patched python-chess boards from the engine registry.
#
# This is the single source of truth for what is legal under each rule.
# The scorer, the pairer, and the SDK all call get_legal_moves() — never
# compute legal moves inline anywhere else.

import functools
from engine.registry import REGISTRY


def get_legal_moves(fen: str, perturbation: str) -> list[str]:
    """
    Return all legal UCI moves for `fen` under the given `perturbation`.

    Args:
        fen:          FEN string of the position to evaluate.
        perturbation: Key from engine.registry.REGISTRY
                      e.g. "bishop_as_rook", "knight_no_l_shape", ...

    Returns:
        List of UCI move strings e.g. ["e2e4", "g1f3", "d1d2"]
        Empty list if the position is terminal or the perturbation is unknown.

    Raises:
        KeyError if `perturbation` is not in REGISTRY.
    """
    if perturbation not in REGISTRY:
        raise KeyError(
            f"Unknown perturbation '{perturbation}'. "
            f"Available: {list(REGISTRY.keys())}"
        )

    board = REGISTRY[perturbation](fen)
    return [move.uci() for move in board.legal_moves]


@functools.lru_cache(maxsize=8192)
def get_legal_moves_cached(fen: str, perturbation: str) -> tuple[str, ...]:
    """
    Cached version — returns a tuple (hashable) instead of a list.
    Use this inside the pairer's inner loop to avoid recomputing the
    same (FEN, perturbation) pair if it appears more than once.
    """
    return tuple(get_legal_moves(fen, perturbation))


def is_move_legal(fen: str, move_uci: str, perturbation: str) -> bool:
    """
    Convenience function: check whether a single UCI move is legal
    under the given perturbation. Used by the SDK scoring function.

    Args:
        fen:          Position to check.
        move_uci:     Move string in UCI notation e.g. "e2e4"
        perturbation: Perturbation key from REGISTRY.

    Returns:
        True if the move is in the perturbed legal set, False otherwise.
    """
    return move_uci in get_legal_moves_cached(fen, perturbation)