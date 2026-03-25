import chess
from engine.base import PerturbedBoard


class CaptureAllPawnsBoard(PerturbedBoard):
    rule_name = "capture_all_pawns"
    category = "win_condition"
    difficulty = "easy"

    def is_game_over(self):
        return not bool(self.pieces(chess.PAWN, not self.turn))

    def is_checkmate(self):
        return False

    def outcome(self):
        if self.is_game_over():
            return chess.Outcome(
                chess.Termination.VARIANT_WIN,
                winner=self.turn
            )
        return None