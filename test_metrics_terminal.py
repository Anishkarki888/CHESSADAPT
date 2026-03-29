# test_metrics_terminal.py
# Run from project root:
#   python test_metrics_terminal.py

from engine.composition.mixins import MoveEvent
from engine.composition.metrics import (
    compliance_rate,
    inhibition_score,
    flexibility_index,
    composite_score,
    MetricsCalculator,
)

# ── Build fake MoveEvents ────────────────────────────────────────────────────
# MoveEvent fields (check mixins.py if any differ):
#   move          : str   — UCI move e.g. "e2e4"
#   is_legal_perturbed  : bool — legal under new rule?
#   is_inhibition_failure: bool — legal in standard chess BUT illegal under rule?
#   category      : str   — perturbation category e.g. "piece_movement"

def make_event(move, is_legal_perturbed, is_inhibition_failure, category):
    e = MoveEvent.__new__(MoveEvent)
    e.move_uci             = move
    e.is_legal_perturbed   = is_legal_perturbed
    e.is_inhibition_failure= is_inhibition_failure
    e.category             = category
    return e


# ── Test scenarios ────────────────────────────────────────────────────────────

# Scenario A: perfect model — always plays legal perturbed moves
perfect = [
    make_event("e2e4", True,  False, "piece_movement"),
    make_event("g1f3", True,  False, "piece_movement"),
    make_event("d2d4", True,  False, "win_condition"),
    make_event("c2c4", True,  False, "turn_structure"),
]

# Scenario B: bad model — always falls back to standard chess (inhibition failures)
failing = [
    make_event("e2e4", False, True,  "piece_movement"),
    make_event("g1f3", False, True,  "piece_movement"),
    make_event("d2d4", False, True,  "win_condition"),
    make_event("c2c4", False, True,  "turn_structure"),
]

# Scenario C: mixed model — good at piece_movement, bad at win_condition
mixed = [
    make_event("e2e4", True,  False, "piece_movement"),
    make_event("g1f3", True,  False, "piece_movement"),
    make_event("d2d4", False, True,  "win_condition"),
    make_event("c2c4", False, False, "turn_structure"),  # illegal but not inhibition failure
]


# ── Run and print ────────────────────────────────────────────────────────────

def print_score(label, events):
    calc   = MetricsCalculator()
    result = calc.compute(events)
    print(f"\n{'─'*50}")
    print(f"Scenario: {label}")
    print(f"  Compliance Rate   : {result.compliance_rate}")
    print(f"  Inhibition Score  : {result.inhibition_score}")
    print(f"  Flexibility Index : {result.flexibility_index}")
    print(f"  Composite Score   : {result.composite_score}")
    print(f"  Total / Legal / Failures: "
          f"{result.total_moves} / {result.legal_moves} / {result.inhibition_failures}")


print_score("Perfect model",  perfect)
print_score("Failing model",  failing)
print_score("Mixed model",    mixed)

print(f"\n{'─'*50}")
print("Expected values:")
print("  Perfect → composite ~1.0")
print("  Failing → composite ~0.0 (low compliance, low inhibition)")
print("  Mixed   → composite ~0.5 (low flexibility pulls score down)")
