"""
pipeline/prompt_builder_metacognition.py

ChessAdapt Metacognition Benchmark — Prompt Builder, Parser, and Scorer.

Theoretical grounding
---------------------
Flavell (1979) identified three metacognitive components:
  1. Knowledge  — awareness of one's own cognitive limits
  2. Monitoring — accurate judgment of current performance
  3. Control    — strategy adjustment upon detecting failure

DeepMind Cognitive Taxonomy (Burnell et al. 2026, Section 7.7) maps these to:
  - Confidence calibration        (monitoring)
  - Error detection               (monitoring)
  - Knowledge boundary awareness  (knowledge)
  - Strategy adjustment           (control)

What this module measures
-------------------------
After making a move under a modified chess rule, the model must report:
  M1 — Confidence rating 1-10               (calibration / monitoring)
  M2 — Self-prediction of move legality     (error detection / monitoring)
  M3 — Which part of the rule was hardest   (knowledge boundary / knowledge)

These three signals produce a metacognitive profile independent of move
correctness. A model that makes the wrong move but reports low confidence
is metacognitively aware. A model that makes the wrong move and reports
high confidence is metacognitively blind — the more dangerous failure mode.

Scoring summary
---------------
  calibration_error = |confidence/10 - int(is_correct)|
  overconfidence    = confidence >= 8 AND move is illegal
  underconfidence   = confidence <= 3 AND move is legal
  error_detection   = legal_prediction matches actual correctness
  prospective_gap   = |pre_difficulty - (10 - confidence)|  [hard tier only]
"""

from typing import Literal

TaskType = Literal["T1", "T2", "T3"]


_META_RESPONSE_FORMAT = """\

Respond in EXACTLY this format — no extra text:
MOVE: [your UCI move]
CONFIDENCE: [1-10, how certain you are this move follows the new rule]
LEGAL_PREDICTION: [YES or NO — do you believe your move is legal under the modified rule?]
HARDEST_PART: [one sentence — which part of the rule was hardest to apply and why]\
"""

_T1_TEMPLATE = """\
You are playing chess with one modified rule:
{rule_description}

Current position (FEN): {fen}
It is {side} to move.

Provide exactly one move in UCI notation that follows the modified rule.
Then answer the reflection questions honestly — your reflection is scored
independently of your move.
{meta_format}\
"""

_T2_TEMPLATE = """\
You are playing chess with one modified rule:
{rule_description}

Current position (FEN): {fen}
It is {side} to move.

Find the best move under this modified rule and provide it in UCI notation.
Then answer the reflection questions honestly — your reflection is scored
independently of move quality.
{meta_format}\
"""

_T3_TEMPLATE = """\
You are playing chess with these modified rules:
{rule_list}

Current position (FEN): {fen}
It is {side} to move.

Provide a sequence of exactly 3 moves in UCI notation, one per line,
applying all modified rules consistently across every move.
Then answer the reflection questions honestly — your reflection is scored
independently of your moves.

MOVES (one per line):
[move 1]
[move 2]
[move 3]

CONFIDENCE: [1-10, how certain you are ALL 3 moves follow the modified rules]
LEGAL_PREDICTION: [YES or NO — do you believe all 3 moves are legal under the modified rules?]
HARDEST_PART: [one sentence — which rule or move in the sequence was hardest to apply and why]\
"""

_T1_PREDICT_FIRST_TEMPLATE = """\
You are about to play chess with one modified rule:
{rule_description}

Before seeing the position, rate how difficult you expect it will be to apply
this rule correctly. Rate 1-10 (1 = trivial, 10 = extremely hard).
PRE_DIFFICULTY: [1-10]

Current position (FEN): {fen}
It is {side} to move.

Provide exactly one legal move in UCI notation.
{meta_format}\
"""


def _side_to_move(fen: str) -> str:
    """Return 'White' or 'Black' from the active-color field of a FEN string."""
    parts = fen.split()
    if len(parts) >= 2:
        return "White" if parts[1] == "w" else "Black"
    return "White"


def build_metacognition_prompt(
    fen: str,
    rule_delta: dict,
    task_type: TaskType,
    variant: str = "A",
    predict_first: bool = False,
) -> str:
    """
    Build the metacognition prompt. Supports Variant A (Named) and B (Geometric).
    """
    side = _side_to_move(fen)
    
    if variant == "B":
        rule_desc = rule_delta.get("geometric_description", "")
        # For T3 B, we list the geometric rules
        if task_type == "T3":
            rules = [f"1. {rule_desc}"]
            if "stacked_geometric_description" in rule_delta:
                rules.append(f"2. {rule_delta['stacked_geometric_description']}")
            rule_list = "\n".join(rules)
        else:
            rule_list = rule_desc # not used for T1/T2 but for consistency
    else:
        rule_desc = rule_delta.get("description", "")
        if task_type == "T3":
            rules = [f"1. {rule_desc}"]
            if "stacked_description" in rule_delta:
                rules.append(f"2. {rule_delta['stacked_description']}")
            rule_list = "\n".join(rules)

    if task_type == "T3":
        return _T3_TEMPLATE.format(fen=fen, side=side, rule_list=rule_list)

    if task_type == "T1" and predict_first:
        return _T1_PREDICT_FIRST_TEMPLATE.format(
            fen=fen, side=side, rule_description=rule_desc, meta_format=_META_RESPONSE_FORMAT
        )

    if task_type == "T1":
        return _T1_TEMPLATE.format(
            fen=fen, side=side, rule_description=rule_desc, meta_format=_META_RESPONSE_FORMAT
        )

    return _T2_TEMPLATE.format(
        fen=fen, side=side, rule_description=rule_desc, meta_format=_META_RESPONSE_FORMAT
    )


def parse_metacognition_response(response: str) -> dict:
    """
    Parse a structured metacognition response from the model.

    Expected response format::

        MOVE: e2e4
        CONFIDENCE: 7
        LEGAL_PREDICTION: YES
        HARDEST_PART: The orthogonal constraint was difficult to track...

    Parameters
    ----------
    response : str
        Raw model output string.

    Returns
    -------
    dict with keys:
        move             : str | None
        confidence       : int | None   (1-10)
        legal_prediction : bool | None
        hardest_part     : str | None
        pre_difficulty   : int | None   (predict_first mode only)
        parse_errors     : list[str]    (fields that failed to parse)

    Unparseable fields are recorded as None and listed in parse_errors.
    They are never silently discarded, preventing selection bias in scoring.
    """
    result = {
        "move": None,
        "confidence": None,
        "legal_prediction": None,
        "hardest_part": None,
        "pre_difficulty": None,
        "parse_errors": [],
    }

    lines = response.strip().splitlines()
    line_map = {}
    for line in lines:
        if ":" in line:
            key, _, value = line.partition(":")
            line_map[key.strip().upper()] = value.strip()

    if "MOVE" in line_map:
        result["move"] = line_map["MOVE"].strip().lower()
    
    # Fallback: regex search for anything that looks like a UCI move (e.g., e2e4)
    if result["move"] is None:
        import re
        match = re.search(r'\b([a-h][1-8][a-h][1-8][qrbn]?)\b', response.lower())
        if match:
            result["move"] = match.group(1)
        else:
            result["parse_errors"].append("move")

    if "CONFIDENCE" in line_map:
        try:
            conf = int(line_map["CONFIDENCE"])
            if 1 <= conf <= 10:
                result["confidence"] = conf
        except ValueError:
            pass
    
    if result["confidence"] is None:
        match = re.search(r'\bconfidence\b.*?\b(\d+)\b', response.lower(), re.DOTALL)
        if match:
            c = int(match.group(1))
            if 1 <= c <= 10:
                result["confidence"] = c
        if result["confidence"] is None:
            result["parse_errors"].append("confidence")

    if "LEGAL_PREDICTION" in line_map:
        val = line_map["LEGAL_PREDICTION"].upper()
        if val in ("YES", "Y", "TRUE"):
            result["legal_prediction"] = True
        elif val in ("NO", "N", "FALSE"):
            result["legal_prediction"] = False
    
    if result["legal_prediction"] is None:
        if re.search(r'legal_prediction\b.*?\b(yes|true|y)\b', response.lower(), re.DOTALL):
            result["legal_prediction"] = True
        elif re.search(r'legal_prediction\b.*?\b(no|false|n)\b', response.lower(), re.DOTALL):
            result["legal_prediction"] = False
        else:
            result["parse_errors"].append("legal_prediction")

    if "HARDEST_PART" in line_map:
        result["hardest_part"] = line_map["HARDEST_PART"]
    else:
        result["parse_errors"].append("hardest_part")

    if "PRE_DIFFICULTY" in line_map:
        try:
            result["pre_difficulty"] = int(line_map["PRE_DIFFICULTY"])
        except ValueError:
            result["parse_errors"].append("pre_difficulty")

    return result


def score_metacognition(parsed: dict, is_correct: bool) -> dict:
    """
    Compute metacognition scores from a parsed response.

    Parameters
    ----------
    parsed : dict
        Output of parse_metacognition_response().
    is_correct : bool
        Whether the model's move was legal under the perturbation.

    Returns
    -------
    dict with keys:
        calibration_error : float | None
            |confidence/10 - correctness|. 0.0 = perfect, 1.0 = worst.
        overconfident     : bool | None
            True when confidence >= 8 and move is illegal.
        underconfident    : bool | None
            True when confidence <= 3 and move is legal.
        error_detection   : bool | None
            True when legal_prediction matches actual correctness.
        prospective_gap   : int | None
            |pre_difficulty - (10 - confidence)|. A large gap indicates
            the model cannot anticipate its own failure modes.
            Only populated when predict_first was used.
    """
    scores = {
        "calibration_error": None,
        "overconfident": None,
        "underconfident": None,
        "error_detection": None,
        "prospective_gap": None,
    }

    conf = parsed.get("confidence")
    legal_pred = parsed.get("legal_prediction")
    pre_diff = parsed.get("pre_difficulty")

    if conf is not None:
        scores["calibration_error"] = abs((conf / 10.0) - float(is_correct))
        scores["overconfident"] = (conf >= 8) and (not is_correct)
        scores["underconfident"] = (conf <= 3) and is_correct

    if legal_pred is not None:
        scores["error_detection"] = (legal_pred == is_correct)

    if pre_diff is not None and conf is not None:
        actual_difficulty = 10 - conf
        scores["prospective_gap"] = abs(pre_diff - actual_difficulty)

    return scores