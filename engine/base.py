import chess


class PerturbedBoard(chess.Board):
    "Perturbed Chess board"
    rule_name = "base"
    category = "base"
    difficulty = "easy"

    def legal_uci_moves(self):
        return [move.uci() for move in self.legal_moves]

    def rule_delta(self):
        return {
            "rule_name": self.rule_name,
            "category": self.category,
            "difficulty": self.difficulty,
        }