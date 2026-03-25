import chess
from engine.base import PerturbedBoard


class PawnForwardCaptureBoard(PerturbedBoard):
    rule_name = "pawn_forward_capture"
    category = "movement"
    difficulty = "hard"

    def generate_pseudo_legal_moves(self, from_mask=chess.BB_ALL, to_mask=chess.BB_ALL):
        # 1. Non-pawn moves
        for move in super().generate_pseudo_legal_moves(from_mask & ~int(self.pieces(chess.PAWN, self.turn)), to_mask):
            yield move

        # 2. Pawn moves (with forward capture)
        pawns = self.pieces(chess.PAWN, self.turn) & from_mask
        if not pawns:
            return

        direction = 8 if self.turn == chess.WHITE else -8
        start_rank = chess.BB_RANK_2 if self.turn == chess.WHITE else chess.BB_RANK_7
        promotion_rank = chess.BB_RANK_8 if self.turn == chess.WHITE else chess.BB_RANK_1

        for sq in chess.scan_forward(int(pawns)):
            # Forward one square (push or capture)
            to_sq = sq + direction
            if 0 <= to_sq < 64:
                # Can move if it's empty OR an enemy piece
                if not (self.occupied_co[self.turn] & chess.BB_SQUARES[to_sq]):
                    if chess.BB_SQUARES[to_sq] & to_mask:
                        if chess.BB_SQUARES[to_sq] & promotion_rank:
                            for pt in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
                                yield chess.Move(sq, to_sq, promotion=pt)
                        else:
                            yield chess.Move(sq, to_sq)

                    # Double push (only if both squares are empty, as per original logic)
                    if chess.BB_SQUARES[sq] & start_rank:
                        two_step = sq + 2 * direction
                        if not (self.occupied & chess.BB_SQUARES[to_sq]) and \
                           not (self.occupied & chess.BB_SQUARES[two_step]):
                            if chess.BB_SQUARES[two_step] & to_mask:
                                yield chess.Move(sq, two_step)

            # Diagonal captures (standard)
            # board.attacks_mask(sq) for pawns depends on the turn
            attacks = self.attacks_mask(sq) & to_mask
            targets = attacks & (int(self.occupied_co[not self.turn]) | (chess.BB_SQUARES[self.ep_square] if self.ep_square else 0))
            
            for target in chess.scan_forward(int(targets)):
                if chess.BB_SQUARES[target] & promotion_rank:
                    for pt in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
                        yield chess.Move(sq, target, promotion=pt)
                else:
                    yield chess.Move(sq, target)