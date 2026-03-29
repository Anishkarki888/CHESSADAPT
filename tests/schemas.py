# tasks/schemas.py
# TaskItem dataclass — the canonical schema for every task in ChessAdapt.
# Every field here maps directly to a column in the Kaggle Benchmarks SDK.

from dataclasses import dataclass, field
from typing import Literal

TaskType      = Literal["T1", "T2", "T3"]
DifficultyTier = Literal["easy", "medium", "hard"]


@dataclass
class TaskItem:
    """
    One benchmark task item.

    Fields
    ------
    fen             : FEN string of the starting position.
    rule_delta      : Dict describing the perturbation(s) applied.
                      Keys: type, perturbation, description,
                            [stacked_perturbation, stacked_description]
    prompt_template : Fully rendered prompt delivered to the model.
    legal_moves     : Precomputed list of legal UCI moves under perturbed rules.
                      This is the ground truth used by the scorer.
    difficulty_tier : "easy" | "medium" | "hard"
    task_type       : "T1" | "T2" | "T3"
    source_game_id  : Lichess game ID for traceability.
    """

    fen             : str
    rule_delta      : dict
    prompt_template : str
    legal_moves     : list[str]
    difficulty_tier : DifficultyTier
    task_type       : TaskType
    source_game_id  : str

    def is_valid(self) -> bool:
        """Quick self-check — used in unit tests."""
        return (
            bool(self.fen)
            and len(self.fen.split()) == 6
            and bool(self.legal_moves)
            and self.task_type in ("T1", "T2", "T3")
            and self.difficulty_tier in ("easy", "medium", "hard")
            and "perturbation" in self.rule_delta
        )
