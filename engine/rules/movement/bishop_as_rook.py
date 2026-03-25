import chess
from engine.base import PerturbedBoard

class BishopAsRookBoard(PerturbedBoard):
    rule_name = "bishop_as_rook"
    category = "movement"
    difficulty = "medium"

    def generate_pseudo_legal_moves(self, from_mask=chess.BB_ALL, to_mask=chess.BB_ALL):
        # 1. Non-bishop moves
        for move in super().generate_pseudo_legal_moves(from_mask & ~int(self.pieces(chess.BISHOP, self.turn)), to_mask):
            yield move

        # 2. Bishop-as-Rook moves
        for sq in self.pieces(chess.BISHOP, self.turn) & from_mask:
            # Temporarily pretend it's a rook to get sliding rook attacks
            original_piece = self.piece_at(sq)
            self.set_piece_at(sq, chess.Piece(chess.ROOK, self.turn))
            attacks = self.attacks_mask(sq) & to_mask
            # Restore original piece
            self.set_piece_at(sq, original_piece)
            
            # Filter out moves to our own pieces (pseudo-legal)
            targets = attacks & ~self.occupied_co[self.turn]
            for to_sq in chess.scan_forward(targets):
                yield chess.Move(sq, to_sq)