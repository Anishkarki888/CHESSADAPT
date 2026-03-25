"validate_move()"

import chess
from engine.registry import get_board


def validate_move(fen: str, rule_name: str, uci: str):
    # perturbed board
    board = get_board(rule_name, fen)
    move = chess.Move.from_uci(uci)

    is_legal = move in board.legal_moves

    # standard chess baseline
    standard_board = chess.Board(fen)
    is_old_rule = move in standard_board.legal_moves

    return {
        "legal": is_legal,
        "is_old_rule": is_old_rule,
        "uci_move": uci,
    }