# pipeline/difficulty.py
# Classifies each (FEN, perturbation) pair as easy / medium / hard.
#
# Logic:
#   1. Get the standard-chess best move via Stockfish (normal rules)
#   2. Get legal moves under the perturbed ruleset via the engine registry
#   3. If the standard best move is still legal → easy   (low inhibition pressure)
#      If it's illegal but not forcing          → medium (model must suppress prior)
#      If it's illegal AND was a forcing move   → hard   (maximum inhibition pressure)
#
# "Forcing" means: the standard best move was a capture, check, or
# delivers mate-in-N — i.e. the move a chess player would find obvious.

import functools
import chess
import chess.engine
import os
from typing import Literal, Optional

from engine.legal_moves import get_legal_moves

DifficultyTier = Literal["easy", "medium", "hard"]

# Path to Stockfish binary — override via env var STOCKFISH_PATH
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")

# Stockfish analysis depth for best-move lookup (shallow is fine here)
ANALYSIS_DEPTH = 12

class DifficultyClassifier:
    """
    Classifies task difficulty by comparing standard-chess best moves
    with perturbed legal sets. Reuses a single Stockfish instance.
    """
    def __init__(self, stockfish_path: str = STOCKFISH_PATH):
        self.stockfish_path = stockfish_path
        self._engine = None

    def __enter__(self):
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
        except Exception as e:
            print(f"WARN: Could not start Stockfish at {self.stockfish_path}: {e}")
            self._engine = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._engine:
            self._engine.quit()
            self._engine = None

    def get_best_move(self, fen: str) -> Optional[str]:
        if not self._engine:
            return None
        try:
            board = chess.Board(fen)
            result = self._engine.play(board, chess.engine.Limit(depth=ANALYSIS_DEPTH))
            return result.move.uci() if result.move else None
        except Exception:
            return None

    def is_forcing(self, fen: str, move_uci: str) -> bool:
        """
        Return True if `move_uci` is a forcing move in the standard position.
        """
        try:
            board = chess.Board(fen)
            move = chess.Move.from_uci(move_uci)
            if move not in board.legal_moves:
                return False

            is_capture = board.is_capture(move)
            board.push(move)
            gives_check = board.is_check()
            gives_mate = board.is_checkmate()

            return is_capture or gives_check or gives_mate
        except Exception:
            return False

    @functools.lru_cache(maxsize=4096)
    def classify(self, fen: str, perturbation: str) -> DifficultyTier:
        std_best = self.get_best_move(fen)
        if std_best is None:
            return "medium"

        perturbed_legal = get_legal_moves(fen, perturbation)
        if std_best in perturbed_legal:
            return "easy"

        if self.is_forcing(fen, std_best):
            return "hard"
        return "medium"

# Stateless versions for one-off calls
def classify(fen: str, perturbation: str) -> DifficultyTier:
    with DifficultyClassifier() as dc:
        return dc.classify(fen, perturbation)
