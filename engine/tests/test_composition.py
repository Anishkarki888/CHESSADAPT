"""
Tests for the composition module.

Covers:
  • RuleComposer — single and stacked rules, push/pop, win conditions
  • MetricsCalculator — compliance, inhibition, flexibility, composite
  • ExperimentRunner — single run, batch run, persistence
"""

import json
import tempfile
from pathlib import Path

import chess
import pytest

from engine.composition.composer import RuleComposer
from engine.composition.metrics import (
    MetricsCalculator,
    compliance_rate,
    inhibition_score,
    flexibility_index,
    composite_score,
)
from engine.composition.mixins import MoveEvent, StateTrackingMixin
from engine.composition.experiment import ExperimentRunner


# ── Helpers ──────────────────────────────────────────────────────────────────

START_FEN = chess.STARTING_FEN


def _make_event(
    legal_perturbed: bool = True,
    legal_standard: bool = True,
    category: str = "movement",
) -> MoveEvent:
    """Create a minimal MoveEvent for metric tests."""
    return MoveEvent(
        fen_before=START_FEN,
        fen_after=START_FEN,
        move_uci="e2e4",
        rule_names=["test_rule"],
        category=category,
        is_legal_perturbed=legal_perturbed,
        is_legal_standard=legal_standard,
        is_inhibition_failure=(legal_standard and not legal_perturbed),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  RuleComposer Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRuleComposerSingle:
    """Single-rule composition should match REGISTRY behavior exactly."""

    def test_single_movement_rule(self):
        """bishop_as_rook via composer == via REGISTRY."""
        from engine.registry import get_board

        fen = "8/8/8/3B4/8/8/8/8 w - - 0 1"
        composer = RuleComposer(fen, ["bishop_as_rook"])
        registry_board = get_board("bishop_as_rook", fen)

        composer_moves = set(composer.legal_uci_moves())
        registry_moves = set(m.uci() for m in registry_board.legal_moves)

        assert composer_moves == registry_moves

    def test_single_turn_structure_rule(self):
        """no_repeat_piece via composer == via REGISTRY."""
        from engine.registry import get_board

        composer = RuleComposer(START_FEN, ["no_repeat_piece"])
        registry_board = get_board("no_repeat_piece", START_FEN)

        composer_moves = set(composer.legal_uci_moves())
        registry_moves = set(m.uci() for m in registry_board.legal_moves)

        assert composer_moves == registry_moves

    def test_single_win_condition(self):
        """capture_all_pawns win detection works via composer."""
        fen_no_black_pawns = "8/8/8/8/8/8/PPPPPPPP/4K3 w - - 0 1"
        composer = RuleComposer(fen_no_black_pawns, ["capture_all_pawns"])
        assert composer.is_game_over()
        assert composer.outcome().winner == chess.WHITE

    def test_rule_delta_single(self):
        composer = RuleComposer(START_FEN, ["bishop_as_rook"])
        delta = composer.rule_delta()
        assert delta["rule_count"] == 1
        assert delta["rules"][0]["rule_name"] == "bishop_as_rook"


class TestRuleComposerStacked:
    """Stacked-rule composition for T3 tasks."""

    def test_movement_plus_turn_structure(self):
        """bishop_as_rook + no_repeat_piece should intersect correctly."""
        from engine.registry import get_board

        composer = RuleComposer(START_FEN, ["bishop_as_rook", "no_repeat_piece"])

        # Initial position: no_repeat_piece has no forbidden square yet,
        # so the intersection should equal bishop_as_rook moves exactly
        bishop_board = get_board("bishop_as_rook", START_FEN)
        bishop_moves = set(m.uci() for m in bishop_board.legal_moves)

        composed = set(composer.legal_uci_moves())

        # Composed moves should be a subset of (or equal to) bishop moves
        # since no_repeat_piece only removes moves from a forbidden square
        # (which is None on the first move)
        assert composed == bishop_moves

    def test_stacked_rule_delta(self):
        composer = RuleComposer(START_FEN, ["bishop_as_rook", "no_repeat_piece"])
        delta = composer.rule_delta()
        assert delta["rule_count"] == 2
        assert "movement" in delta["combined_category"]
        assert "turn_structure" in delta["combined_category"]

    def test_push_updates_all_boards(self):
        """After push, FEN should advance on all internal boards."""
        composer = RuleComposer(START_FEN, ["queen_no_backwards", "no_repeat_piece"])

        # e2e4 should be legal under both rules
        result = composer.push("e2e4")
        assert result["legal"] is True

        # FEN should have changed
        assert composer.fen != START_FEN

        # After pushing e2e4, the pawn at e4 should be forbidden for
        # no_repeat_piece — verify it's not in legal moves
        legal = set(composer.legal_uci_moves())
        e4_moves = {m for m in legal if m.startswith("e4")}
        assert len(e4_moves) == 0, "Piece on e4 should be forbidden by no_repeat_piece"

    def test_pop_restores_state(self):
        composer = RuleComposer(START_FEN, ["bishop_as_rook", "no_repeat_piece"])
        original_fen = composer.fen
        composer.push("e2e4")
        composer.pop()
        assert composer.fen == original_fen

    def test_unknown_rule_raises(self):
        with pytest.raises(ValueError, match="Unknown rule"):
            RuleComposer(START_FEN, ["totally_fake_rule"])

    def test_empty_rules_raises(self):
        with pytest.raises(ValueError, match="At least one rule"):
            RuleComposer(START_FEN, [])


class TestRuleComposerValidation:
    """Move validation with inhibition tracking."""

    def test_validate_legal_move(self):
        composer = RuleComposer(START_FEN, ["bishop_as_rook"])
        result = composer.validate_move("e2e4")
        assert result["legal"] is True
        assert result["is_old_rule"] is True
        assert result["is_inhibition_failure"] is False

    def test_validate_illegal_move(self):
        """A move illegal under the composed rules but legal in standard chess."""
        # Bishop at d5 — under bishop_as_rook, diagonal moves are illegal
        fen = "8/8/8/3B4/8/8/8/4K2k w - - 0 1"
        composer = RuleComposer(fen, ["bishop_as_rook"])
        result = composer.validate_move("d5e6")  # diagonal — illegal under bishop_as_rook
        assert result["legal"] is False
        assert result["is_old_rule"] is True  # legal in standard chess
        assert result["is_inhibition_failure"] is True

    def test_event_log_populated(self):
        composer = RuleComposer(START_FEN, ["bishop_as_rook"])
        composer.validate_move("e2e4")
        composer.validate_move("d2d4")

        events = composer.get_event_log()
        assert len(events) == 2
        assert events[0].move_uci == "e2e4"
        assert events[1].move_uci == "d2d4"


# ═══════════════════════════════════════════════════════════════════════════
#  MetricsCalculator Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMetrics:
    def test_compliance_rate_all_legal(self):
        events = [_make_event(legal_perturbed=True) for _ in range(5)]
        assert compliance_rate(events) == 1.0

    def test_compliance_rate_none_legal(self):
        events = [_make_event(legal_perturbed=False) for _ in range(5)]
        assert compliance_rate(events) == 0.0

    def test_compliance_rate_mixed(self):
        events = [
            _make_event(legal_perturbed=True),
            _make_event(legal_perturbed=False),
        ]
        assert compliance_rate(events) == 0.5

    def test_compliance_rate_empty(self):
        assert compliance_rate([]) == 0.0

    def test_inhibition_score_no_failures(self):
        events = [_make_event(legal_perturbed=True, legal_standard=True)]
        assert inhibition_score(events) == 1.0

    def test_inhibition_score_all_failures(self):
        events = [_make_event(legal_perturbed=False, legal_standard=True)]
        assert inhibition_score(events) == 0.0

    def test_inhibition_score_empty(self):
        assert inhibition_score([]) == 1.0

    def test_flexibility_index_single_category(self):
        events_by_cat = {"movement": [_make_event()]}
        assert flexibility_index(events_by_cat) == 1.0

    def test_flexibility_index_uniform(self):
        events_by_cat = {
            "movement": [_make_event(legal_perturbed=True, category="movement")],
            "win_condition": [_make_event(legal_perturbed=True, category="win_condition")],
        }
        assert flexibility_index(events_by_cat) == 1.0

    def test_flexibility_index_divergent(self):
        events_by_cat = {
            "movement": [_make_event(legal_perturbed=True, category="movement")],
            "win_condition": [_make_event(legal_perturbed=False, category="win_condition")],
        }
        flexibility = flexibility_index(events_by_cat)
        # stdev of [1.0, 0.0] = 0.5 → flexibility = 0.5
        assert flexibility == pytest.approx(0.5)

    def test_composite_score_weights(self):
        # 1.0 * 0.50 + 1.0 * 0.30 + 1.0 * 0.20 = 1.0
        assert composite_score(1.0, 1.0, 1.0) == 1.0
        # 0.0 * 0.50 + 0.0 * 0.30 + 0.0 * 0.20 = 0.0
        assert composite_score(0.0, 0.0, 0.0) == 0.0
        # 0.8 * 0.50 + 0.6 * 0.30 + 1.0 * 0.20 = 0.40 + 0.18 + 0.20 = 0.78
        assert composite_score(0.8, 0.6, 1.0) == pytest.approx(0.78)

    def test_metrics_calculator_end_to_end(self):
        events = [
            _make_event(legal_perturbed=True, legal_standard=True, category="movement"),
            _make_event(legal_perturbed=False, legal_standard=True, category="movement"),
            _make_event(legal_perturbed=True, legal_standard=True, category="win_condition"),
        ]
        calc = MetricsCalculator()
        score = calc.compute(events)

        assert score.total_moves == 3
        assert score.legal_moves == 2
        assert score.inhibition_failures == 1
        assert score.compliance_rate == pytest.approx(2 / 3, abs=0.01)
        assert score.inhibition_score == pytest.approx(2 / 3, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════
#  ExperimentRunner Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestExperimentRunner:
    def test_run_single_t1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(output_dir=tmpdir)
            result = runner.run_single(
                fen=START_FEN,
                rule_names=["bishop_as_rook"],
                model_moves=["e2e4"],
                task_type="T1",
                metadata={"model": "test"},
            )

            assert result.task_type == "T1"
            assert result.score.total_moves == 1
            assert result.score.compliance_rate == 1.0  # e2e4 is legal

            # Verify JSON file was saved
            files = list(Path(tmpdir).glob("*.json"))
            assert len(files) == 1

            # Verify JSON is valid
            data = json.loads(files[0].read_text())
            assert data["experiment_id"] == result.experiment_id

    def test_run_single_illegal_move(self):
        """Model plays a move that is illegal under the perturbation."""
        fen = "8/8/8/3B4/8/8/8/4K2k w - - 0 1"
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(output_dir=tmpdir)
            result = runner.run_single(
                fen=fen,
                rule_names=["bishop_as_rook"],
                model_moves=["d5e6"],  # diagonal — illegal
                task_type="T1",
            )
            assert result.score.compliance_rate == 0.0
            assert result.score.inhibition_score == 0.0

    def test_run_batch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(output_dir=tmpdir)
            tasks = [
                {
                    "fen": START_FEN,
                    "rule_names": ["bishop_as_rook"],
                    "model_moves": ["e2e4"],
                    "task_type": "T1",
                },
                {
                    "fen": START_FEN,
                    "rule_names": ["queen_no_backwards"],
                    "model_moves": ["d2d4"],
                    "task_type": "T1",
                },
            ]
            results = runner.run_batch(tasks)
            assert len(results) == 2

            summary = runner.summary()
            assert summary["total_experiments"] == 2

    def test_run_batch_error_handling(self):
        """Batch should not crash on a single bad task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(output_dir=tmpdir)
            tasks = [
                {
                    "fen": START_FEN,
                    "rule_names": ["bishop_as_rook"],
                    "model_moves": ["e2e4"],
                    "task_type": "T1",
                },
                {
                    "fen": START_FEN,
                    "rule_names": ["nonexistent_rule"],
                    "model_moves": ["e2e4"],
                    "task_type": "T1",
                },
            ]
            results = runner.run_batch(tasks)
            assert len(results) == 2
            assert "error" in results[1].metadata

    def test_summary_by_task_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(output_dir=tmpdir)
            runner.run_single(START_FEN, ["bishop_as_rook"], ["e2e4"], "T1")
            runner.run_single(START_FEN, ["bishop_as_rook"], ["d2d4"], "T2")

            summary = runner.summary()
            assert "T1" in summary["by_task_type"]
            assert "T2" in summary["by_task_type"]

    def test_no_disk_save(self):
        runner = ExperimentRunner(save_to_disk=False)
        result = runner.run_single(START_FEN, ["bishop_as_rook"], ["e2e4"], "T1")
        assert result.experiment_id  # still works, just no file


class TestStateTrackingMixin:
    def test_event_log_lifecycle(self):
        tracker = StateTrackingMixin()
        tracker._init_state_tracking(rule_names=["test"], category="test")

        assert tracker.event_count == 0

        tracker._record_event(
            fen_before=START_FEN,
            fen_after=START_FEN,
            move_uci="e2e4",
            is_legal_perturbed=True,
            is_legal_standard=True,
        )

        assert tracker.event_count == 1
        events = tracker.get_event_log()
        assert len(events) == 1
        assert events[0].move_uci == "e2e4"

        tracker.clear_event_log()
        assert tracker.event_count == 0


# ── Run directly ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
