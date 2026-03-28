import chess
import pytest

from engine.rules.turn_structure import NoRepeatPieceBoard, TwoMovesPerTurnBoard


def test_noRepeatPieceBoard():
    board = NoRepeatPieceBoard()

    # Initial move: e2 → e4
    move1 = chess.Move.from_uci("e2e4")
    board.push(move1)

    # Now the pawn is on e4, so moving FROM e4 should be forbidden
    legal_moves = list(board.generate_legal_moves())

    forbidden_square = move1.to_square
    illegal_moves = [m for m in legal_moves if m.from_square == forbidden_square]

    assert len(illegal_moves) == 0, "Piece that just moved should not be allowed to move again"

    # Make another move (black plays something random)
    move2 = chess.Move.from_uci("a7a6")
    board.push(move2)

    # Now restriction should apply to a6
    legal_moves = list(board.generate_legal_moves())
    forbidden_square = move2.to_square

    illegal_moves = [m for m in legal_moves if m.from_square == forbidden_square]
    assert len(illegal_moves) == 0

    # Undo last move → restriction should revert
    board.pop()

    legal_moves = list(board.generate_legal_moves())
    # Now e4 should still be restricted (because last move is again e2e4)
    illegal_moves = [m for m in legal_moves if m.from_square == move1.to_square]
    assert len(illegal_moves) == 0

    # Undo again → no restriction
    board.pop()
    legal_moves = list(board.generate_legal_moves())

    # Now everything should be normal (pawn can move from e2)
    assert any(m.from_square == chess.E2 for m in legal_moves)


def test_two_moves_per_turn():
    board = TwoMovesPerTurnBoard()

    # White makes first move
    move1 = chess.Move.from_uci("e2e4")
    board.push(move1)

    # Turn should still be WHITE (same player gets second move)
    assert board.turn == chess.WHITE, "Player should get two moves per turn"

    # White makes second move
    move2 = chess.Move.from_uci("g1f3")
    board.push(move2)

    # Now turn should switch to BLACK
    assert board.turn == chess.BLACK, "Turn should switch after two moves"

    # Black first move
    move3 = chess.Move.from_uci("a7a6")
    board.push(move3)

    # Still black's turn
    assert board.turn == chess.BLACK

    # Black second move
    move4 = chess.Move.from_uci("a6a5")
    board.push(move4)

    # Now should switch back to white
    assert board.turn == chess.WHITE

    # Test pop behavior
    board.pop()  # undo black's second move
    assert board.turn == chess.BLACK, "Undoing second move should keep turn as black"

    board.pop()  # undo black's first move
    assert board.turn == chess.BLACK, "Undoing first move should restore turn correctly"

    board.pop()  # undo white's second move
    assert board.turn == chess.WHITE

    board.pop()  # undo white's first move
    assert board.turn == chess.WHITE