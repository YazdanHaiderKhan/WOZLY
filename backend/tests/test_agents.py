"""Tests for EMA, spaced repetition, and agent logic (no LLM calls needed)."""
import pytest
from app.state.cls import compute_ema, compute_next_review
from app.agents.assessment import aggregate_topic_scores, determine_next_action
from datetime import datetime, timedelta


# ── EMA Correctness ────────────────────────────────────────────────────────────

class TestEMA:
    def test_basic_formula(self):
        """P(t) = α × O(t) + (1−α) × P(t−1) with α=0.3"""
        result = compute_ema(prev_score=0.6, observed_score=0.8, alpha=0.3)
        expected = 0.3 * 0.8 + 0.7 * 0.6
        assert abs(result - expected) < 0.001

    def test_first_score_from_zero(self):
        result = compute_ema(prev_score=0.0, observed_score=1.0, alpha=0.3)
        assert abs(result - 0.3) < 0.001

    def test_perfect_score_increases(self):
        prev = 0.5
        result = compute_ema(prev, 1.0, 0.3)
        assert result > prev

    def test_zero_score_decreases(self):
        prev = 0.7
        result = compute_ema(prev, 0.0, 0.3)
        assert result < prev

    def test_same_score_unchanged(self):
        """If observed == prev, EMA stays the same."""
        prev = 0.65
        result = compute_ema(prev, prev, 0.3)
        assert abs(result - prev) < 0.001

    def test_high_alpha_more_weight_on_recent(self):
        """Higher α = more weight on new score."""
        result_high = compute_ema(0.4, 1.0, alpha=0.9)
        result_low  = compute_ema(0.4, 1.0, alpha=0.1)
        assert result_high > result_low

    def test_result_bounded_0_1(self):
        """EMA must always be in [0, 1]."""
        for obs in [0.0, 0.5, 1.0]:
            for prev in [0.0, 0.5, 1.0]:
                result = compute_ema(prev, obs, 0.3)
                assert 0.0 <= result <= 1.0


# ── Spaced Repetition ─────────────────────────────────────────────────────────

class TestSpacedRepetition:
    def test_mastered_doubles_interval(self):
        """score >= 0.8 → double interval."""
        next_review = compute_next_review(score=0.9, current_interval_days=4)
        expected_min = datetime.utcnow() + timedelta(days=7)  # 4*2=8, allow some tolerance
        assert next_review > expected_min

    def test_partial_adds_one_day(self):
        """0.5 <= score < 0.8 → interval + 1."""
        next_review = compute_next_review(score=0.65, current_interval_days=3)
        expected = datetime.utcnow() + timedelta(days=3)
        assert next_review >= expected

    def test_fail_schedules_next_day(self):
        """score < 0.5 → review next day."""
        next_review = compute_next_review(score=0.3, current_interval_days=10)
        tomorrow = datetime.utcnow() + timedelta(hours=20)
        assert next_review >= tomorrow


# ── Assessment Scoring ────────────────────────────────────────────────────────

class TestAssessmentScoring:
    def test_aggregate_topic_scores_averaging(self):
        questions = [
            {"id": "q1", "type": "multiple_choice", "topic": "Arrays"},
            {"id": "q2", "type": "multiple_choice", "topic": "Arrays"},
            {"id": "q3", "type": "short_answer", "topic": "Trees"},
        ]
        scores = {"q1": 1.0, "q2": 0.0, "q3": 0.8}
        result = aggregate_topic_scores(questions, scores)
        assert abs(result["Arrays"] - 0.5) < 0.001
        assert abs(result["Trees"] - 0.8) < 0.001

    def test_determine_next_action_continue(self):
        assert determine_next_action({"A": 0.9, "B": 0.85}) == "continue"

    def test_determine_next_action_review(self):
        result = determine_next_action({"A": 0.9, "B": 0.3})
        assert result in ("review", "replan")

    def test_determine_next_action_replan(self):
        """Majority of topics failing → replan."""
        result = determine_next_action({"A": 0.2, "B": 0.1, "C": 0.9})
        assert result in ("review", "replan")

    def test_empty_topic_scores(self):
        assert determine_next_action({}) == "continue"


# ── API auth tests (sync, no DB needed) ───────────────────────────────────────

class TestSecurity:
    def test_jwt_encode_decode(self):
        from app.core.security import create_access_token, decode_token
        token = create_access_token("user-abc-123")
        decoded = decode_token(token)
        assert decoded == "user-abc-123"

    def test_invalid_token_returns_none(self):
        from app.core.security import decode_token
        assert decode_token("not-a-valid-token") is None

    def test_password_hash_verify(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("securepassword123")
        assert verify_password("securepassword123", hashed)
        assert not verify_password("wrongpassword", hashed)
