import pytest
from evaluation.response_parser import ResponseParser

@pytest.mark.eval
@pytest.mark.parametrize("input_text, expected", [
    ("e2e4", ["e2e4"]),
    ("1. e2e4\n2. g1f3", ["e2e4", "g1f3"]),
    ("```e2e4```", ["e2e4"]),
    ("My move is e2e4 because ...", ["e2e4"]),
    ("e7e8q", ["e7e8q"]),
    ("a2a4 and b2b4", ["a2a4", "b2b4"]),
    ("E2E4", ["e2e4"]),
])
def test_response_parser_extracts_correctly(input_text, expected):
    parser = ResponseParser()
    assert parser.extract(input_text) == expected

def test_response_parser_empty_input():
    parser = ResponseParser()
    assert parser.extract("") == []
    assert parser.extract("   ") == []

def test_response_parser_max_moves_limit():
    parser = ResponseParser()
    input_text = "e2e4 g1f3 d2d4 c2c4"
    assert len(parser.extract(input_text, max_moves=2)) == 2
    assert parser.extract(input_text, max_moves=2) == ["e2e4", "g1f3"]

def test_response_parser_deduplication():
    parser = ResponseParser()
    input_text = "e2e4 e2e4 g1f3"
    assert parser.extract(input_text) == ["e2e4", "g1f3"]

def test_extract_single():
    parser = ResponseParser()
    assert parser.extract_single("My move is e2e4.") == "e2e4"
    assert parser.extract_single("No move here.") is None

def test_promotion_moves():
    parser = ResponseParser()
    assert parser.extract("a7a8q") == ["a7a8q"]
    assert parser.extract("a7a8R") == ["a7a8r"]
