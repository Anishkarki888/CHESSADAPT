import pytest
import chess
from engine.rules.win_conditions import CaptureAllPawnsBoard, CentreRaceBoard

@pytest.mark.engine
class TestWinConditions:
    def test_capture_all_pawns(self):
        # Start from normal position → game should NOT be over
        board = CaptureAllPawnsBoard()
        assert not board.is_game_over()
        assert board.outcome() is None

        # Create position where BLACK has no pawns
        fen_no_black_pawns = "8/8/8/8/8/8/PPPPPPPP/4K3 w - - 0 1"
        board = CaptureAllPawnsBoard(fen_no_black_pawns)

        # White to move → opponent (black) has no pawns → white wins
        assert board.is_game_over()
        outcome = board.outcome()
        assert outcome is not None
        assert outcome.winner == chess.WHITE
        assert outcome.termination == chess.Termination.VARIANT_WIN

        # Checkmate should ALWAYS be disabled
        assert not board.is_checkmate()

    def test_capture_all_pawns_black_wins(self):
        # Position where WHITE has no pawns
        fen_no_white_pawns = "4k3/pppppppp/8/8/8/8/8/8 b - - 0 1"
        board = CaptureAllPawnsBoard(fen_no_white_pawns)

        # Black to move → opponent (white) has no pawns → black wins
        assert board.is_game_over()
        outcome = board.outcome()
        assert outcome.winner == chess.BLACK

    @pytest.mark.parametrize("move_uci, expected_winner", [
        ("e2e4", chess.WHITE),
        ("d2d4", None), # D4 is not winning square
        ("a2a3", None), # No win
    ])
    def test_centre_race_board_parametrized(self, move_uci, expected_winner):
        board = CentreRaceBoard()
        board.push(chess.Move.from_uci(move_uci))
        if expected_winner is not None:
            assert board.is_game_over()
            assert board.outcome().winner == expected_winner
        else:
            assert not board.is_game_over()

    def test_centre_race_black_win(self):
        # Now test BLACK winning via E5
        board = CentreRaceBoard()
        board.push(chess.Move.from_uci("a2a3"))  # white
        board.push(chess.Move.from_uci("e7e5"))  # black hits E5
        assert board.is_game_over()
        assert board.outcome().winner == chess.BLACK

    def test_centre_race_edge_case_no_pawns(self):
        # Centre Race should still work if pawns are missing
        # White King at e3
        fen = "4k3/8/8/8/8/4K3/8/8 w - - 0 1"
        board = CentreRaceBoard(fen)
        # Move White King to e4
        board.push(chess.Move.from_uci("e3e4"))
        assert board.is_game_over()
        assert board.outcome().winner == chess.WHITE