import chess
import pytest
from engine.rules.turn_structure import NoRepeatPieceBoard, TwoMovesPerTurnBoard

@pytest.mark.engine
class TestTurnStructure:
    def test_no_repeat_piece_board(self):
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

        # Undo last move → restriction should revert to e4
        board.pop()
        legal_moves = list(board.generate_legal_moves())
        assert not any(m.from_square == move1.to_square for m in legal_moves)

    def test_two_moves_per_turn(self):
        board = TwoMovesPerTurnBoard()

        # White makes first move
        board.push(chess.Move.from_uci("e2e4"))
        assert board.turn == chess.WHITE, "Player should get two moves per turn"

        # White makes second move
        board.push(chess.Move.from_uci("g1f3"))
        assert board.turn == chess.BLACK, "Turn should switch after two moves"

        # Black first move
        board.push(chess.Move.from_uci("a7a6"))
        assert board.turn == chess.BLACK

        # Black second move
        board.push(chess.Move.from_uci("a6a5"))
        assert board.turn == chess.WHITE

    def test_two_moves_per_turn_pop(self):
        board = TwoMovesPerTurnBoard()
        board.push(chess.Move.from_uci("e2e4")) # W1
        board.push(chess.Move.from_uci("g1f3")) # W2
        
        board.pop() # Undo W2
        assert board.turn == chess.WHITE
        
        board.pop() # Undo W1
        assert board.turn == chess.WHITE

    def test_two_moves_per_turn_consecutive_color(self):
        board = TwoMovesPerTurnBoard()
        board.push(chess.Move.from_uci("e2e4")) # W1
        # Check that it's still White's turn
        assert board.turn == chess.WHITE
        # Check that we can make ANOTHER White move
        assert any(board.piece_at(m.from_square).color == chess.WHITE for m in board.legal_moves)