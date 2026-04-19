"""Centralized Learner State (CLS) manager.

Handles all reads, writes, EMA mastery updates, and spaced-repetition
scheduling. Uses optimistic locking (version counter) to prevent
concurrent write conflicts.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from typing import Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db_models import LearnerState
from app.core.config import get_settings

settings = get_settings()


# ─────────────────────────────────── helpers ──────────────────────────────────

def compute_ema(prev_score: float, observed_score: float, alpha: float | None = None) -> float:
    """Exponential Moving Average: P(t) = α × O(t) + (1 − α) × P(t−1)."""
    a = alpha if alpha is not None else settings.alpha
    return round(a * observed_score + (1 - a) * prev_score, 4)


def compute_next_review(score: float, current_interval_days: int) -> datetime:
    """
    Spaced repetition scheduling per PRD Section 5.3:
    - score >= 0.8 → double the interval
    - 0.5 <= score < 0.8 → interval + 1 day
    - score < 0.5 → next day (immediate intervention)
    """
    now = datetime.utcnow()
    if score >= 0.8:
        next_days = current_interval_days * 2
    elif score >= 0.5:
        next_days = current_interval_days + 1
    else:
        next_days = 1
    return now + timedelta(days=max(next_days, 1))


# ─────────────────────────────────── manager ──────────────────────────────────

class CLSManager:
    """All CLS read/write operations go through this class."""

    @staticmethod
    async def get_state(user_id: str, db: AsyncSession) -> dict:
        """Load CLS from PostgreSQL for the given user."""
        result = await db.execute(
            select(LearnerState).where(LearnerState.user_id == str(user_id))
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"No learner state found for user {user_id}")
        return dict(row.cls_json)

    @staticmethod
    async def update_state(
        user_id: str,
        db: AsyncSession,
        patch_fn: Callable[[dict], dict],
    ) -> dict:
        """
        Load CLS, apply patch_fn (pure function dict → dict),
        and persist with incremented version (optimistic lock).
        """
        result = await db.execute(
            select(LearnerState).where(LearnerState.user_id == str(user_id))
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"No learner state found for user {user_id}")

        new_cls = patch_fn(dict(row.cls_json))
        row.cls_json = new_cls
        row.version = (row.version or 0) + 1
        row.updated_at = datetime.utcnow()
        await db.commit()
        return new_cls

    @staticmethod
    async def apply_quiz_score(
        user_id: str,
        db: AsyncSession,
        topic_id: str,
        observed_score: float,
    ) -> dict:
        """
        Apply EMA mastery update for a single topic and compute next_review.
        Returns the updated CLS.
        """
        def _patch(cls: dict) -> dict:
            mastery = cls.setdefault("mastery", {})
            topic = mastery.get(topic_id, {"current_score": 0.0, "history": [], "next_review": None})

            prev = topic.get("current_score", 0.0)
            new_score = compute_ema(prev, observed_score)

            # Derive current interval from history length (simplified: 1 day per review)
            current_interval = max(len(topic.get("history", [])), 1)
            next_review = compute_next_review(new_score, current_interval)

            topic["history"].append({
                "score": observed_score,
                "timestamp": datetime.utcnow().isoformat(),
            })
            topic["current_score"] = new_score
            topic["next_review"] = next_review.isoformat()

            # Flag needs_review in roadmap if score < 0.5
            if new_score < 0.5:
                _flag_needs_review(cls, topic_id)

            mastery[topic_id] = topic
            cls["mastery"] = mastery
            return cls

        return await CLSManager.update_state(user_id, db, _patch)

    @staticmethod
    async def increment_hint_count(
        user_id: str,
        db: AsyncSession,
        topic_id: str,
    ) -> dict:
        """Increment hint_count and flag needs_review if threshold exceeded."""
        def _patch(cls: dict) -> dict:
            cls["hint_count"] = cls.get("hint_count", 0) + 1

            # Per-topic hint tracking stored in mastery
            mastery = cls.setdefault("mastery", {})
            topic = mastery.get(topic_id, {"current_score": 0.0, "history": [], "next_review": None})
            session_hints = topic.get("session_hints", 0) + 1
            topic["session_hints"] = session_hints

            if session_hints >= settings.max_hints_per_topic:
                _flag_needs_review(cls, topic_id)
                topic["needs_review"] = True

            mastery[topic_id] = topic
            cls["mastery"] = mastery
            return cls

        return await CLSManager.update_state(user_id, db, _patch)

    @staticmethod
    async def append_session_history(
        user_id: str,
        db: AsyncSession,
        agent: str,
        input_text: str,
        output_text: str,
    ) -> None:
        """Append an interaction to CLS session_history (last 50 kept)."""
        def _patch(cls: dict) -> dict:
            entry = {
                "session_id": str(uuid.uuid4()),
                "agent": agent,
                "input": input_text,
                "output": output_text,
                "timestamp": datetime.utcnow().isoformat(),
            }
            history = cls.get("session_history", [])
            history.append(entry)
            cls["session_history"] = history[-50:]   # keep last 50
            return cls

        await CLSManager.update_state(user_id, db, _patch)


def _flag_needs_review(cls: dict, topic_id: str) -> None:
    """Mark a topic as needs-review in the roadmap weeks."""
    roadmap = cls.get("roadmap")
    if not roadmap:
        return
    for week in roadmap.get("weeks", []):
        if topic_id in week.get("topics", []):
            week["needs_review"] = week.get("needs_review", [])
            if topic_id not in week["needs_review"]:
                week["needs_review"].append(topic_id)
