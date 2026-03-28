import pytest
import chess
from evaluation.prompt_builder import PromptBuilder, _RULE_DESCRIPTIONS

@pytest.mark.eval
def test_prompt_builder_t1_produces_valid_string():
    builder = PromptBuilder()
    fen = chess.STARTING_FEN
    prompt = builder.build(fen, ["bishop_as_rook"], "T1")
    assert isinstance(prompt, str)
    assert fen in prompt
    assert "White" in prompt
    assert "Bishops now move like Rooks" in prompt
    assert "ONE legal move" in prompt

def test_prompt_builder_t2_produces_valid_string():
    builder = PromptBuilder()
    fen = chess.STARTING_FEN
    prompt = builder.build(fen, ["knight_two_squares"], "T2")
    assert isinstance(prompt, str)
    assert fen in prompt
    assert "White" in prompt
    assert "Knights now move exactly 2 squares" in prompt
    assert "BEST strategic move" in prompt

def test_prompt_builder_t3_produces_valid_string():
    builder = PromptBuilder()
    fen = chess.STARTING_FEN
    prompt = builder.build(fen, ["bishop_as_rook", "knight_two_squares"], "T3")
    assert isinstance(prompt, str)
    assert fen in prompt
    assert "White" in prompt
    assert "bishop_as_rook" in prompt
    assert "knight_two_squares" in prompt
    assert "exactly 3 legal moves" in prompt

def test_unknown_task_type_raises_value_error():
    builder = PromptBuilder()
    with pytest.raises(ValueError, match="Unknown task_type"):
        builder.build(chess.STARTING_FEN, ["bishop_as_rook"], "T4")

def test_all_rules_have_descriptions():
    from engine.registry import REGISTRY
    for rule_name in REGISTRY.keys():
        assert rule_name in _RULE_DESCRIPTIONS, f"Rule {rule_name} missing description"
        assert len(_RULE_DESCRIPTIONS[rule_name]) > 10
