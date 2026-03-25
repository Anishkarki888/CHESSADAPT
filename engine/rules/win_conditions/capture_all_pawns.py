import chess
from engine.base import PerturbedBoard


class CaptureAllPawnsBoard(PerturbedBoard):
    rule_name = "capture_all_pawns"
    category = "win_condition"
    difficulty = "easy"

    def is_game_over(self):
        # opponent has no pawns → current player wins
        return not bool(self.pieces(chess.PAWN, not self.turn))

    def is_checkmate(self):
        # disable standard checkmate
        return False

    def outcome(self):
        if self.is_game_over():
            return chess.Outcome(
                termination=chess.Termination.VARIANT_WIN,
                winner=self.turn
            )
        return None