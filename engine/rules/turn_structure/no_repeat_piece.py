import chess
from engine.base import PerturbedBoard


class NoRepeatPieceBoard(PerturbedBoard):
    rule_name = "no_repeat_piece"
    category = "turn_structure"
    difficulty = "medium"

    def __init__(self, fen=None):
        super().__init__(fen)
        self._forbidden_stack = []

    def push(self, move):
        super().push(move)
        self._forbidden_stack.append(move.to_square)

    def pop(self):
        self._forbidden_stack.pop()
        return super().pop()

    def generate_legal_moves(self, from_mask=chess.BB_ALL, to_mask=chess.BB_ALL):
        forbidden = self._forbidden_stack[-1] if self._forbidden_stack else None

        for move in super().generate_legal_moves(from_mask, to_mask):
            if forbidden is not None and move.from_square == forbidden:
                continue
            yield move