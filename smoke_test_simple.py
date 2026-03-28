"""
Smoke test for ChessAdapt evaluation pipeline (Kaggle context).
This script demonstrates the end-to-end flow: Load → Prompt → Parse → Score.
"""

import json
from evaluation.task_generator import _build_task_item
from evaluation.prompt_builder import PromptBuilder
from evaluation.response_parser import ResponseParser
from engine.composition.experiment import ExperimentRunner

def smoke_test():
    print("🚀 Starting ChessAdapt Smoke Test...\n")

    # 1. Mock Position (Standard Middlegame)
    fen = "r1bqk2r/pp2bppp/2nppn2/8/3NP3/2N5/PPP1BPPP/R1BQ1RK1 w kq - 0 1"
    rule_names = ["bishop_as_rook"]
    task_type = "T1"

    print(f"📍 FEN: {fen}")
    print(f"📜 Rule: {rule_names[0]} ({PromptBuilder.describe_rule(rule_names[0])})")

    # 2. Build Task & Prompt (Injection)
    task = _build_task_item(fen, rule_names, task_type)
    prompt = task["prompt"]
    print("\n--- Prompt Preview ---")
    print(prompt[:300] + "...")

    # 3. Mock Model Response
    # In a real run, this would be: response = llm.generate(prompt)
    mock_response = "Thinking step-by-step: The bishop at e2 now moves like a rook. It can capture on e7 or move to d2, f2, etc. My move is e2e7."
    print(f"\n🤖 Mock Model Output: \"{mock_response}\"")

    # 4. Extract Move (Parsing)
    parser = ResponseParser()
    model_moves = parser.extract(mock_response, max_moves=1)
    print(f"🔍 Extracted Move: {model_moves}")

    # 5. Score Move (Metrics wiring: compliance, inhibition, flexibility)
    runner = ExperimentRunner(save_to_disk=False)
    result = runner.run_single(
        fen=fen,
        rule_names=rule_names,
        model_moves=model_moves,
        task_type=task_type
    )

    print("\n--- Final Scores ---")
    print(f"✅ Compliance:  {result.score.compliance_rate:.2f}")
    print(f"🚫 Inhibition:  {result.score.inhibition_score:.2f}")
    print(f"🧠 Composite:   {result.score.composite_score:.2f}")

    if result.score.compliance_rate > 0:
        print("\n✨ SMOKE TEST PASSED: End-to-end pipeline works correctly.")
    else:
        print("\n❌ SMOKE TEST FAILED: Unintended scoring result.")

if __name__ == "__main__":
    smoke_test()
