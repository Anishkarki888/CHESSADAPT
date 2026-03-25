from engine.registry import get_board

fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

board = get_board("bishop_as_rook", fen)

print(board.legal_moves)