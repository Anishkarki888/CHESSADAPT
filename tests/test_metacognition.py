import pytest
import chess
from pipeline.prompt_builder_metacognition import (
    build_metacognition_prompt,
    parse_metacognition_response,
    score_metacognition
)
from engine.composition.metrics import MetacognitionCalculator
from engine.composition.mixins import MoveEvent

@pytest.mark.eval
def test_metacognition_prompt_builder():
    fen = chess.STARTING_FEN
    rule_delta = {"description": "Bishops move like Rooks"}
    
    # Test T1 Standard
    prompt_t1 = build_metacognition_prompt(fen, rule_delta, "T1")
    assert fen in prompt_t1
    assert "CONFIDENCE:" in prompt_t1
    assert "Bishops move like Rooks" in prompt_t1

    # Test T1 Predict First (Hard)
    prompt_t1_pref = build_metacognition_prompt(fen, rule_delta, "T1", predict_first=True)
    assert "PRE_DIFFICULTY:" in prompt_t1_pref

def test_metacognition_parser_success():
    response = """
    MOVE: e2e4
    CONFIDENCE: 8
    LEGAL_PREDICTION: YES
    HARDEST_PART: The jumping rule was complex.
    """
    parsed = parse_metacognition_response(response)
    assert parsed["move"] == "e2e4"
    assert parsed["confidence"] == 8
    assert parsed["legal_prediction"] is True
    assert parsed["hardest_part"] == "The jumping rule was complex."
    assert not parsed["parse_errors"]

def test_metacognition_parser_messy_format():
    response = "I think the move is MOVE: g1f3. CONFIDENCE is 5. LEGAL_PREDICTION: no."
    parsed = parse_metacognition_response(response)
    assert parsed["move"] == "g1f3"
    assert parsed["confidence"] == 5
    assert parsed["legal_prediction"] is False

def test_metacognition_scorer_calibration():
    # Model is confident but wrong (High calibration error)
    parsed = {"confidence": 9, "legal_prediction": True}
    scores = score_metacognition(parsed, is_correct=False)
    assert scores["calibration_error"] == 0.9
    assert scores["overconfident"] is True

    # Model is doubtful and wrong (Low calibration error)
    parsed = {"confidence": 2, "legal_prediction": False}
    scores = score_metacognition(parsed, is_correct=False)
    assert scores["calibration_error"] == 0.2
    assert scores["overconfident"] is False
    assert scores["error_detection"] is True

def test_metacognition_calculator_aggregation():
    # Mock some events
    events = [
        MoveEvent(is_legal_perturbed=True, extra={"confidence": 10, "legal_prediction": True}),
        MoveEvent(is_legal_perturbed=False, extra={"confidence": 9, "legal_prediction": True}), # Overconfident
        MoveEvent(is_legal_perturbed=False, extra={"confidence": 2, "legal_prediction": False}), # Well calibrated
    ]
    
    report = MetacognitionCalculator.compute(events)
    
    # 3 total, 1 overconfident -> 0.3333
    assert report.overconfidence_rate == 0.3333
    # 3 total, 2 correct detections (10/True and 2/False) -> 0.6667
    assert report.error_detection_accuracy == 0.6667
    assert isinstance(report.calibration_error, float)
