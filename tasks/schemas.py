# tasks/schemas.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class TaskItem:
    fen: str
    rule_delta: Dict[str, Any]
    prompt_template: str
    legal_moves: List[str]
    difficulty_tier: str
    task_type: str
    source_game_id: str
