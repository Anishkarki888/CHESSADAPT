import chess
from engine.base import PerturbedBoard


class TwoMovesPerTurnBoard(PerturbedBoard):
    rule_name = "two_moves_per_turn"
    category = "turn_structure"
    difficulty = "hard"

    def __init__(self, fen=None):
        super().__init__(fen)
        self._move_count_stack = []  # True = first move, False = second move

    def push(self, move):
        is_first_move = not self._move_count_stack or not self._move_count_stack[-1]

        current_turn = self.turn
        super().push(move)

        if is_first_move:
            self.turn = current_turn

        self._move_count_stack.append(is_first_move)

    def pop(self):
        was_first = self._move_count_stack.pop()

        if was_first:
            self.turn = not self.turn
            return super().pop()
        else:
            return super().pop()