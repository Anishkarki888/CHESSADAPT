"cached legal move generation"

from functools import lru_cache
from engine.registry import get_board


@lru_cache(maxsize=10000)
def get_legal_moves(fen: str, rule_name: str):
    board = get_board(rule_name, fen)
    return tuple(move.uci() for move in board.legal_moves)