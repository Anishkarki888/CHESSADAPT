import chess
from engine.base import PerturbedBoard


class PawnForwardCaptureBoard(PerturbedBoard):
    rule_name = "pawn_forward_capture"
    category = "movement"
    difficulty = "hard"

    def generate_pseudo_legal_moves(self, from_mask=chess.BB_ALL, to_mask=chess.BB_ALL):
        # keep non-pawn moves
        for move in super().generate_pseudo_legal_moves(from_mask, to_mask):
            if self.piece_type_at(move.from_square) == chess.PAWN:
                continue
            yield move

        pawns = self.pieces(chess.PAWN, self.turn)
        direction = 8 if self.turn == chess.WHITE else -8
        start_rank = 1 if self.turn == chess.WHITE else 6
        promotion_rank = 7 if self.turn == chess.WHITE else 0

        for sq in pawns:
            rank = chess.square_rank(sq)
            one_step = sq + direction

            if 0 <= one_step < 64:
                if self.occupied & chess.BB_SQUARES[one_step]:
                    # forward capture
                    if self.occupied_co[not self.turn] & chess.BB_SQUARES[one_step]:
                        yield chess.Move(sq, one_step)
                else:
                    # normal push
                    yield chess.Move(sq, one_step)

                    # double push
                    if rank == start_rank:
                        two_step = sq + 2 * direction
                        if not (self.occupied & chess.BB_SQUARES[two_step]):
                            yield chess.Move(sq, two_step)

            # diagonal captures (standard)
            for df in (-1, 1):
                f = chess.square_file(sq) + df
                r = rank + (1 if self.turn == chess.WHITE else -1)

                if 0 <= f < 8 and 0 <= r < 8:
                    target = chess.square(f, r)
                    if self.occupied_co[not self.turn] & chess.BB_SQUARES[target]:
                        yield chess.Move(sq, target)