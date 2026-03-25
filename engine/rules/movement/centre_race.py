import chess
from engine.base import PerturbedBoard


class CentreRaceBoard(PerturbedBoard):
    rule_name = "centre_race"
    category = "win_condition"
    difficulty = "medium"

    def __init__(self, fen=None):
        super().__init__(fen)
        self._centre_winner = None

    def push(self, move):
        mover = self.turn
        super().push(move)

        if move.to_square in (chess.E4, chess.E5):
            self._centre_winner = mover

    def pop(self):
        super().pop()
        self._centre_winner = None

    def is_game_over(self):
        return self._centre_winner is not None

    def outcome(self):
        if self._centre_winner is not None:
            return chess.Outcome(
                chess.Termination.VARIANT_WIN,
                winner=self._centre_winner
            )
        return None