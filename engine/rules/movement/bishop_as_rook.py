import chess
from engine.base import PerturbedBoard


class BishopAsRookBoard(PerturbedBoard):
    rule_name = "bishop_as_rook"
    category = "movement"
    difficulty = "medium"

    def generate_pseudo_legal_moves(self, from_mask=chess.BB_ALL, to_mask=chess.BB_ALL):
        for move in super().generate_pseudo_legal_moves(from_mask, to_mask):
            if self.piece_type_at(move.from_square) == chess.BISHOP:
                continue
            yield move

        bishops = self.pieces(chess.BISHOP, self.turn)

        for sq in bishops:
            attacks = (
                chess.BB_RANK_ATTACKS[sq][chess.BB_ALL & self.occupied]
                | chess.BB_FILE_ATTACKS[sq][chess.BB_ALL & self.occupied]
            )
            attacks &= ~self.occupied_co[self.turn]

            for target in chess.scan_forward(attacks):
                yield chess.Move(sq, target)