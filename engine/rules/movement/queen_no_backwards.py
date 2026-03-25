import chess
from engine.base import PerturbedBoard


class QueenNoBackwardsBoard(PerturbedBoard):
    rule_name = "queen_no_backwards"
    category = "movement"
    difficulty = "easy"

    def generate_pseudo_legal_moves(self, from_mask=chess.BB_ALL, to_mask=chess.BB_ALL):
        for move in super().generate_pseudo_legal_moves(from_mask, to_mask):
            if self.piece_type_at(move.from_square) != chess.QUEEN:
                yield move
                continue

            from_rank = chess.square_rank(move.from_square)
            to_rank = chess.square_rank(move.to_square)

            if self.turn == chess.WHITE:
                if to_rank >= from_rank:
                    yield move
            else:
                if to_rank <= from_rank:
                    yield move