import chess
from engine.base import PerturbedBoard


class TwoMovesPerTurnBoard(PerturbedBoard):
    rule_name = "two_moves_per_turn"
    category = "turn_structure"
    difficulty = "hard"

    def __init__(self, fen=chess.STARTING_FEN, *args, **kwargs):
        super().__init__(fen, *args, **kwargs)
        self._first_move_stack = []

    def push(self, move):
        is_first_move = not self._first_move_stack or not self._first_move_stack[-1]

        current_turn = self.turn
        super().push(move)

        if is_first_move:
            # undo turn flip → same player moves again
            self.turn = current_turn

        self._first_move_stack.append(is_first_move)

    def pop(self):
        was_first = self._first_move_stack.pop()

        if was_first:
            # restore state expected by super().pop()
            self.turn = not self.turn
            return super().pop()
        else:
            return super().pop()