import chess
from engine.registry import get_board

def test_bishop_as_rook():
    # Bishop at d5 on empty board
    fen = "8/8/8/3B4/8/8/8/8 w - - 0 1"
    board = get_board("bishop_as_rook", fen)
    legal = set(move.uci() for move in board.legal_moves)
    
    # Expected: Rook moves from d5 (d1-d8, a5-h5, except d5 itself)
    # Ranks: d1, d2, d3, d4, d6, d7, d8
    # Files: a5, b5, c5, e5, f5, g5, h5
    expected = {
        "d5d1", "d5d2", "d5d3", "d5d4", "d5d6", "d5d7", "d5d8",
        "d5a5", "d5b5", "d5c5", "d5e5", "d5f5", "d5g5", "d5h5"
    }
    
    print("Bishop as Rook legal moves:", sorted(list(legal)))
    assert legal == expected, f"Expected {expected}, got {legal}"
    
    # Test blockers
    fen = "8/8/8/3B1p2/8/8/8/8 w - - 0 1" # Enemy pawn at f5
    board = get_board("bishop_as_rook", fen)
    legal = set(move.uci() for move in board.legal_moves)
    # Should include d5f5 but not d5g5, d5h5
    assert "d5f5" in legal
    assert "d5g5" not in legal
    assert "d5h5" not in legal

def test_knight_two_squares():
    # Knight at d5
    fen = "8/8/8/3N4/8/8/8/8 w - - 0 1"
    board = get_board("knight_two_squares", fen)
    legal = set(move.uci() for move in board.legal_moves)
    
    # Expected: 2 squares away in any direction (including diagonals)
    # d5 -> b3, b5, b7, d3, d7, f3, f5, f7
    expected = {"d5b3", "d5b5", "d5b7", "d5d3", "d5d7", "d5f3", "d5f5", "d5f7"}
    
    print("Knight Two Squares legal moves:", sorted(list(legal)))
    assert legal == expected, f"Expected {expected}, got {legal}"

def test_queen_no_backwards():
    # White Queen at d5
    fen = "8/8/8/3Q4/8/8/8/8 w - - 0 1"
    board = get_board("queen_no_backwards", fen)
    legal = set(move.uci() for move in board.legal_moves)
    
    # Check that it cannot move to rank 4, 3, 2, 1
    for move_uci in legal:
        to_sq = chess.parse_square(move_uci[2:4])
        assert chess.square_rank(to_sq) >= chess.square_rank(chess.D5), f"Queen moved backwards: {move_uci}"

    # Black Queen at d5
    fen = "8/8/8/3q4/8/8/8/8 b - - 0 1"
    board = get_board("queen_no_backwards", fen)
    legal = set(move.uci() for move in board.legal_moves)
    
    for move_uci in legal:
        to_sq = chess.parse_square(move_uci[2:4])
        assert chess.square_rank(to_sq) <= chess.square_rank(chess.D5), f"Black Queen moved backwards: {move_uci}"

def test_pawn_forward_capture():
    # White Pawn at d2
    fen = "8/8/8/8/8/8/3P4/8 w - - 0 1"
    # Actually starting pos is rank 2.
    fen = "8/8/8/8/8/8/3P4/8 w - - 0 1"
    # Wait, rank 2 is index 1.
    # 8/8/8/8/8/8/3P4/8 means pawn is at d2 (rank 2).
    board = get_board("pawn_forward_capture", fen)
    legal = set(move.uci() for move in board.legal_moves)
    
    # Should be able to double push to d4, single push to d3
    assert "d2d3" in legal
    assert "d2d4" in legal
    
    # Test forward capture
    fen = "8/8/8/8/8/3p4/3P4/4K2k w - - 0 1" # Black pawn at d3
    board = get_board("pawn_forward_capture", fen)
    legal = set(move.uci() for move in board.legal_moves)
    
    # Should be able to capture d2d3
    assert "d2d3" in legal
    # Double push d2d4 should be blocked
    assert "d2d4" not in legal

    # Test promotion
    fen = "8/3P4/4K3/8/8/8/4k3/8 w - - 0 1" # White pawn at d7
    board = get_board("pawn_forward_capture", fen)
    legal = set(move.uci() for move in board.legal_moves)
    assert "d7d8q" in legal
    assert "d7d8n" in legal

if __name__ == "__main__":
    test_bishop_as_rook()
    test_knight_two_squares()
    test_queen_no_backwards()
    test_pawn_forward_capture()
    print("All movement rule tests passed!")
