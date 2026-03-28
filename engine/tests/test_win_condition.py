import chess
from engine.rules.win_conditions import CaptureAllPawnsBoard
from engine.rules.win_conditions import CentreRaceBoard



def test_capture_all_pawns():
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

    # Flip turn → now black to move, opponent (white) HAS pawns → game continues
    board.turn = chess.BLACK
    assert not board.is_game_over()
    assert board.outcome() is None

    # Now remove WHITE pawns instead
    fen_no_white_pawns = "4k3/pppppppp/8/8/8/8/8/8 b - - 0 1"
    board = CaptureAllPawnsBoard(fen_no_white_pawns)

    # Black to move → opponent (white) has no pawns → black wins
    assert board.is_game_over()
    outcome = board.outcome()

    assert outcome.winner == chess.BLACK

    # Checkmate should ALWAYS be disabled
    assert not board.is_checkmate()




def test_centreRaceBoard():
    board = CentreRaceBoard()

    # Normal move → no win
    move1 = chess.Move.from_uci("a2a3")
    board.push(move1)

    assert not board.is_game_over()
    assert board.outcome() is None

    # Move to center square (E4) → WHITE should win
    move2 = chess.Move.from_uci("e2e4")
    board.push(move2)

    assert board.is_game_over()

    outcome = board.outcome()
    assert outcome is not None
    assert outcome.winner == chess.WHITE
    assert outcome.termination == chess.Termination.VARIANT_WIN

    # Pop → should undo win
    board.pop()
    assert not board.is_game_over()
    assert board.outcome() is None

    # Now test BLACK winning via E5
    board = CentreRaceBoard()

    board.push(chess.Move.from_uci("a2a3"))  # white
    board.push(chess.Move.from_uci("e7e5"))  # black hits E5

    assert board.is_game_over()

    outcome = board.outcome()
    assert outcome.winner == chess.BLACK

    # Ensure stack consistency after multiple pops
    board.pop()
    assert not board.is_game_over()

    board.pop()
    assert not board.is_game_over()