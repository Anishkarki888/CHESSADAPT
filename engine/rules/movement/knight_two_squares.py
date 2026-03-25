import chess
from engine.base import PerturbedBoard


class KnightTwoSquaresBoard(PerturbedBoard):
    rule_name = "knight_two_squares"
    category = "movement"
    difficulty = "medium"

    _ATTACKS = None

    @classmethod
    def _build_attack_table(cls):
        table = [0] * 64

        for sq in range(64):
            rank = chess.square_rank(sq)
            file = chess.square_file(sq)

            attacks = 0
            for dr in (-2, 0, 2):
                for df in (-2, 0, 2):
                    if dr == 0 and df == 0:
                        continue

                    r = rank + dr
                    f = file + df

                    if 0 <= r < 8 and 0 <= f < 8:
                        attacks |= chess.BB_SQUARES[chess.square(f, r)]

            table[sq] = attacks

        return table

    def generate_pseudo_legal_moves(self, from_mask=chess.BB_ALL, to_mask=chess.BB_ALL):
        if self._ATTACKS is None:
            type(self)._ATTACKS = self._build_attack_table()

        # 1. Non-knight moves
        for move in super().generate_pseudo_legal_moves(from_mask & ~int(self.pieces(chess.KNIGHT, self.turn)), to_mask):
            yield move

        # 2. Knight-two-squares moves
        for sq in self.pieces(chess.KNIGHT, self.turn) & from_mask:
            attacks = self._ATTACKS[sq] & to_mask
            targets = attacks & ~int(self.occupied_co[self.turn])

            for target in chess.scan_forward(int(targets)):
                yield chess.Move(sq, target)