import pytest
import chess
from engine.registry import get_board

@pytest.mark.engine
class TestMovementRules:
    def test_bishop_as_rook(self, isolated_bishop_fen):
        # isolated_bishop_fen should be d5 if fixture is correct.
        # Wait, my fixture was "8/8/8/3B4/8/8/8/8 w - - 0 1" which is d5.
        board = get_board("bishop_as_rook", isolated_bishop_fen)
        legal = set(move.uci() for move in board.legal_moves)
        
        # Expected: Rook moves from d5 (d1-d8, a5-h5, except d5 itself)
        expected = {
            "d5d1", "d5d2", "d5d3", "d5d4", "d5d6", "d5d7", "d5d8",
            "d5a5", "d5b5", "d5c5", "d5e5", "d5f5", "d5g5", "d5h5"
        }
        assert legal == expected

    @pytest.mark.parametrize("fen, move_uci, should_be_legal", [
        ("8/8/8/3B1p2/8/8/8/8 w - - 0 1", "d5f5", True), # Capture enemy pawn at f5
        ("8/8/8/3B1p2/8/8/8/8 w - - 0 1", "d5g5", False), # Blocked by f5
        ("8/8/8/3B1P2/8/8/8/8 w - - 0 1", "d5f5", False), # Blocked by own piece at f5
    ])
    def test_bishop_as_rook_edge_cases(self, fen, move_uci, should_be_legal):
        board = get_board("bishop_as_rook", fen)
        legal = [m.uci() for m in board.legal_moves]
        assert (move_uci in legal) == should_be_legal

    def test_knight_two_squares(self):
        # Knight at d5
        fen = "8/8/8/3N4/8/8/8/8 w - - 0 1"
        board = get_board("knight_two_squares", fen)
        legal = set(move.uci() for move in board.legal_moves)
        
        # Expected: 2 squares away in any direction (including diagonals)
        # d5 -> b3, b5, b7, d3, d7, f3, f5, f7
        expected = {"d5b3", "d5b5", "d5b7", "d5d3", "d5d7", "d5f3", "d5f5", "d5f7"}
        assert legal == expected

    @pytest.mark.parametrize("fen, color, is_white", [
        ("8/8/8/3Q4/8/8/8/8 w - - 0 1", chess.WHITE, True),
        ("8/8/8/3q4/8/8/8/8 b - - 0 1", chess.BLACK, False),
    ])
    def test_queen_no_backwards(self, fen, color, is_white):
        board = get_board("queen_no_backwards", fen)
        legal = set(move.uci() for move in board.legal_moves)
        
        for move_uci in legal:
            to_sq = chess.parse_square(move_uci[2:4])
            from_sq = chess.parse_square(move_uci[:2])
            if is_white:
                # White rank must not decrease
                assert chess.square_rank(to_sq) >= chess.square_rank(from_sq), f"White Queen moved backwards: {move_uci}"
            else:
                # Black rank must not increase
                assert chess.square_rank(to_sq) <= chess.square_rank(from_sq), f"Black Queen moved backwards: {move_uci}"

    def test_pawn_forward_capture(self):
        # White Pawn at d2
        fen = "8/8/8/8/8/8/3P4/8 w - - 0 1"
        board = get_board("pawn_forward_capture", fen)
        legal = set(move.uci() for move in board.legal_moves)
        
        assert "d2d3" in legal
        assert "d2d4" in legal # Double push still allowed from rank 2
        
        # Test forward capture
        fen = "8/8/8/8/8/3p4/3P4/4K2k w - - 0 1" # Black pawn at d3
        board = get_board("pawn_forward_capture", fen)
        legal = set(move.uci() for move in board.legal_moves)
        
        # Should be able to capture d2d3
        assert "d2d3" in legal
        # Double push d2d4 should be blocked by d3
        assert "d2d4" not in legal

    def test_pawn_forward_capture_promotion(self):
        # Test promotion
        fen = "8/3P4/4K3/8/8/8/4k3/8 w - - 0 1" # White pawn at d7
        board = get_board("pawn_forward_capture", fen)
        legal = set(move.uci() for move in board.legal_moves)
        assert "d7d8q" in legal
        assert "d7d8n" in legal
