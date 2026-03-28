import pytest
import chess
from engine.registry import REGISTRY, get_board

@pytest.mark.engine
def test_registry_contains_all_rules():
    expected_rules = [
        "bishop_as_rook",
        "knight_two_squares",
        "queen_no_backwards",
        "pawn_forward_capture",
        "capture_all_pawns",
        "centre_race",
        "two_moves_per_turn",
        "no_repeat_piece",
    ]
    for rule in expected_rules:
        assert rule in REGISTRY

def test_get_board_returns_correct_class():
    for rule, cls in REGISTRY.items():
        board = get_board(rule, chess.STARTING_FEN)
        assert isinstance(board, cls)
        assert board.rule_name == rule

def test_get_board_raises_for_unknown_rule():
    with pytest.raises(ValueError, match="Unknown rule"):
        get_board("non_existent_rule", chess.STARTING_FEN)

@pytest.mark.parametrize("rule_name", list(REGISTRY.keys()))
def test_all_rules_produce_valid_board(rule_name):
    board = get_board(rule_name, chess.STARTING_FEN)
    assert board.is_valid()
    assert board.fen() == chess.STARTING_FEN
