import pytest
import chess
from engine.registry import REGISTRY

@pytest.fixture
def start_fen():
    return chess.STARTING_FEN

@pytest.fixture
def isolated_bishop_fen():
    # White bishop on d4, some space around it
    return "8/8/8/3B4/8/8/8/8 w - - 0 1"

@pytest.fixture
def all_rule_names():
    return list(REGISTRY.keys())
