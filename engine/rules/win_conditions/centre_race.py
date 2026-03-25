import chess
from engine.base import PerturbedBoard


class CentreRaceBoard(PerturbedBoard):
    rule_name = "centre_race"
    category = "win_condition"
    difficulty = "medium"

    def __init__(self, fen=None):
        super().__init__(fen)
        self._winner_stack = []

    def push(self, move):
        mover = self.turn
        super().push(move)

        winner = None
        if move.to_square in (chess.E4, chess.E5):
            winner = mover

        self._winner_stack.append(winner)

    def pop(self):
        self._winner_stack.pop()
        return super().pop()

    def _current_winner(self):
        return self._winner_stack[-1] if self._winner_stack else None

    def is_game_over(self):
        return self._current_winner() is not None

    def outcome(self):
        winner = self._current_winner()
        if winner is not None:
            return chess.Outcome(
                termination=chess.Termination.VARIANT_WIN,
                winner=winner
            )
        return None