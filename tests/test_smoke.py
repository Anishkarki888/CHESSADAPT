import pytest
import chess
from engine.registry import REGISTRY

@pytest.mark.smoke
def test_import_chess():
    board = chess.Board()
    assert board.is_valid()

@pytest.mark.smoke
def test_registry_not_empty():
    assert len(REGISTRY) > 0
