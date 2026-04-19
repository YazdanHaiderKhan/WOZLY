"""Pedagogical Tutor Agent — Socratic hint-ladder with SSE streaming.

Follows a strict 4-step hint ladder:
  Level 1 — Ask what the learner already knows
  Level 2 — Provide a conceptual analogy
  Level 3 — Give a partial worked example
  Level 4 — Reveal the final step (only after 3 prior hints without progress)

Never provides direct answers or writes complete code.
All hints cite relevant roadmap resources.
"""
from __future__ import annotations
from typing import AsyncIterator
from app.core.llm_client import chat_complete, stream_complete
from app.agents.curator import curate_single_topic

SYSTEM_PROMPT = """You are Wozly's Pedagogical Tutor — a helpful learning assistant.

YOUR RULES:
1. Provide partial answers and clear conceptual explanations to help the learner, but do not solve the entire problem for them instantly.
2. You may write code snippets to illustrate concepts, but avoid writing the complete final code they need without explaining it.
3. Use the current hint level as a rough guide to scale your help:
   - Level 1: Validate what they know and provide a foundational explanation or hint.
   - Level 2: Give a real-world conceptual analogy or intermediate context.
   - Level 3: Provide a partial worked example or a relevant code snippet.
   - Level 4: Give the detailed answer or direct key insight if they are stuck.
4. Try to reference or cite one of the provided resources.
5. Keep your responses concise (3-5 sentences), readable, and encouraging.
6. End with a helpful guiding question if they still need to complete a step themselves.

CURRENT HINT LEVEL: {hint_level}
TOPIC: {topic}
RESOURCES:
{resources}

CONVERSATION HISTORY:
{history}"""


def _build_system_prompt(hint_level: int, topic: str, resources: list[dict], history: list[dict]) -> str:
    resource_text = "\n".join(
        f"  - [{r.get('type', 'article').upper()}] {r.get('title', '')}: {r.get('url', '')}"
        for r in resources[:3]
    ) or "  (No specific resources available — use your knowledge)"

    history_text = "\n".join(
        f"  {m['role'].upper()}: {m['content']}"
        for m in (history or [])[-10:]  # last 10 for context window efficiency
    ) or "  (First message in this session)"

    return SYSTEM_PROMPT.format(
        hint_level=hint_level,
        topic=topic,
        resources=resource_text,
        history=history_text,
    )


def _normalize_history(history: list[dict]) -> list[dict]:
    """Ensure roles are OpenAI-compatible (user/assistant/system)."""
    normalized = []
    for msg in history or []:
        role = msg.get("role", "user")
        if role == "agent":
            role = "assistant"
        if role not in ("system", "user", "assistant"):
            role = "user"
        normalized.append({"role": role, "content": msg.get("content", "")})
    return normalized


async def get_hint(
    user_message: str,
    topic_id: str,
    hint_count: int,
    history: list[dict],
    resources: list[dict],
) -> tuple:
    """Non-streaming hint generation."""
    hint_level = min((hint_count % 4) + 1, 4)
    system = _build_system_prompt(hint_level, topic_id, resources, history)

    # Combine for full history
    messages = (
        [{"role": "system", "content": system}]
        + _normalize_history(history)
        + [{"role": "user", "content": user_message}]
    )

    from app.core.llm_client import chat_complete_messages
    hint_text = await chat_complete_messages(
        messages=messages,
        role="tutor",
        temperature=0.5,
        max_tokens=600,
        json_mode=False,
    )
    return hint_text, hint_level


async def stream_hint(
    user_message: str,
    topic_id: str,
    hint_count: int,
    history: list[dict],
    resources: list[dict],
) -> AsyncIterator[str]:
    """Streaming SSE hint generation — yields token chunks."""
    hint_level = min((hint_count % 4) + 1, 4)
    system = _build_system_prompt(hint_level, topic_id, resources, history)

    # Combine for full history
    messages = (
        [{"role": "system", "content": system}]
        + _normalize_history(history)
        + [{"role": "user", "content": user_message}]
    )

    from app.core.llm_client import stream_complete_messages
    async for chunk in stream_complete_messages(messages=messages, role="tutor"):
        yield chunk


async def handle_tutor_chat(
    user_id: str,
    topic_id: str,
    user_message: str,
    history: list[dict],
    cls: dict,
) -> dict:
    """
    Full non-streaming tutor interaction.
    Returns hint text, updated hint_count, hint_level, and resources.
    """
    domain = cls.get("profile", {}).get("domain", "")
    knowledge_level = cls.get("profile", {}).get("knowledge_level", "beginner")
    hint_count = cls.get("hint_count", 0)

    # Get resources for context
    resources = await curate_single_topic(topic_id, knowledge_level, domain)

    hint_text, hint_level = await get_hint(
        user_message=user_message,
        topic_id=topic_id,
        hint_count=hint_count,
        history=history,
        resources=resources,
    )

    return {
        "hint": hint_text,
        "resources": resources,
        "hint_count": hint_count + 1,
        "hint_level": hint_level,
    }
