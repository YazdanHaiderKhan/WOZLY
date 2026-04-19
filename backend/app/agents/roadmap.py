"""Roadmap Agent — generates personalized weekly learning curricula.

Output schema (3 levels deep):
  Roadmap
  └── Week  (week_title, week_objective, what_user_should_know_after)
      └── Section  (section_title)
          ├── content  (explanation, code_example)
          ├── resources  (per-section docs/videos)
          └── practice  (open-ended homework tasks)
"""
import json
import re
import asyncio
from app.core.config import get_settings
from app.core.llm_client import chat_complete

_settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Roadmap Skeleton Prompt
# Generates: weeks + sections (titles only). Content is filled by the Curator.
# ─────────────────────────────────────────────────────────────────────────────

ROADMAP_SYSTEM = """\
You are Wozly's Roadmap Agent — an expert curriculum architect.

Given a learner profile, generate a structured weekly roadmap with sections per week.

STRICT OUTPUT RULES:
1. Generate exactly N weeks (from duration_weeks).
2. Each week must have 3–5 sections.
3. Sections are ordered from foundational to advanced within the week.
4. week_objective: one sentence describing the week's purpose.
5. what_user_should_know_after: 3–5 concrete bullet outcomes.
6. Section titles are concise topic names (not full sentences).
7. Return ONLY valid JSON. No markdown fences. No reasoning text.

JSON SCHEMA:
{
  "weeks": [
    {
      "week_number": 1,
      "week_title": "string",
      "week_objective": "string",
      "what_user_should_know_after": ["string", "string", "string"],
      "status": "active",
      "sections": [
        { "section_number": 1, "section_title": "string" },
        { "section_number": 2, "section_title": "string" }
      ]
    }
  ]
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Section Content Prompt
# Fills: explanation + code_example for one section
# ─────────────────────────────────────────────────────────────────────────────

SECTION_CONTENT_SYSTEM = """\
You are an elite technical educator writing content for Wozly, a personalized AI learning platform.

For the given section title, domain, and learner level, write:
1. explanation: A clear, engaging explanation (150–250 words). Explain the "Why" and "How". Include real-world context and practical insight. Do NOT just define the term.
2. code_example: A production-quality code snippet (15–30 lines) with meaningful inline comments. Set language appropriately (e.g. "python", "cpp", "javascript"). Set caption to one sentence describing what the snippet shows. Use null if the section is conceptual and code would not add value.

Return ONLY a JSON object. No markdown. No explanation outside JSON.

Schema:
{
  "explanation": "string",
  "code_example": {
    "language": "string",
    "code": "string",
    "caption": "string"
  }
}

Or if no code applies:
{
  "explanation": "string",
  "code_example": null
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Section Resources Prompt
# Fills: resources list for one section
# ─────────────────────────────────────────────────────────────────────────────

SECTION_RESOURCES_SYSTEM = """\
You are a curriculum research specialist at Wozly.

For the given section title, suggest 2–3 high-quality learning resources. 
Prefer official documentation, well-known tutorial sites (MDN, GeeksForGeeks, cplusplus.com, docs.python.org, React docs, etc.), and reputable YouTube educators (Fireship, Traversy Media, The Cherno, CodeWithHarry etc.).

IMPORTANT: Use REAL, ACCURATE URLs that actually exist. Do not invent URLs.
If you are not sure of the exact URL, use the homepage of the resource instead (e.g. https://developer.mozilla.org).

Return ONLY a JSON array. No markdown. No explanation.

Schema:
[
  {
    "title": "string",
    "url": "string",
    "type": "documentation" | "article" | "video" | "tutorial",
    "duration_minutes": null or integer (only for videos)
  }
]
"""

# ─────────────────────────────────────────────────────────────────────────────
# Section Practice Prompt
# Fills: practice questions list for one section
# ─────────────────────────────────────────────────────────────────────────────

SECTION_PRACTICE_SYSTEM = """\
You are a coding instructor writing take-home homework tasks for Wozly learners.

For the given section title and learner level, write 1–2 open-ended practice tasks.
These are offline written/coding exercises — NOT multiple choice. 
They should be concrete and completable without grading (e.g. "Write a program that...", "Create a function that...").

Return ONLY a JSON array. No markdown.

Schema:
[
  {
    "question": "string",
    "type": "written",
    "difficulty": "easy" | "medium" | "hard"
  }
]
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helper: parse JSON from LLM output
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json(raw: str, fallback):
    """Strip reasoning/markdown and parse JSON. Returns fallback on failure."""
    cleaned = re.sub(r"<reasoning>.*?</reasoning>", "", raw, flags=re.DOTALL)
    cleaned = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", cleaned, flags=re.DOTALL).strip()
    # Try full parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Try to extract first { } or [ ] block
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return fallback


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Generate roadmap skeleton (weeks + section titles)
# ─────────────────────────────────────────────────────────────────────────────

async def generate_roadmap(cls: dict) -> dict:
    """
    Generate or re-generate the full roadmap skeleton from the CLS.
    Returns: { "weeks": [ { week_number, week_title, week_objective,
                             what_user_should_know_after, status, sections: [...] } ] }
    """
    profile = cls.get("profile", {})
    mastery = cls.get("mastery", {})

    mastery_summary = "\n".join(
        f"  - {topic}: {data.get('current_score', 0.0):.2f}"
        for topic, data in mastery.items()
    ) or "  (No prior mastery — first roadmap)"

    user_message = (
        f"Learner Profile:\n"
        f"  Goal: {profile.get('goal', 'Learn the subject')}\n"
        f"  Domain: {profile.get('domain', 'General')}\n"
        f"  Level: {profile.get('knowledge_level', 'beginner')}\n"
        f"  Duration: {profile.get('duration_weeks', 4)} weeks\n"
        f"  Prior Knowledge: {', '.join(profile.get('prior_knowledge', [])) or 'None'}\n\n"
        f"Current Mastery:\n{mastery_summary}\n\n"
        f"Generate the personalized roadmap now."
    )

    for attempt in range(2):
        try:
            raw = await chat_complete(
                system=ROADMAP_SYSTEM,
                user=user_message,
                role="roadmap",
                temperature=0.3,
                max_tokens=3000,
                json_mode=True,
            )
            parsed = _parse_json(raw, {})
            weeks = parsed.get("weeks", [])
            if not weeks:
                raise ValueError("Roadmap returned empty weeks list")
            # Normalize statuses
            for i, week in enumerate(weeks):
                week["status"] = "active" if i == 0 else "pending"
                # Ensure sections list exists
                if "sections" not in week:
                    week["sections"] = []
            print(f"[Roadmap] Generated {len(weeks)} weeks successfully.")
            return {"weeks": weeks}
        except Exception as e:
            print(f"[Roadmap] Attempt {attempt+1} failed: {e}")

    # Hard fallback
    return _fallback_roadmap(profile.get("domain", "the subject"), profile.get("duration_weeks", 4))


def _fallback_roadmap(domain: str, num_weeks: int = 4) -> dict:
    """Minimal valid roadmap when LLM fails completely."""
    weeks = []
    for w in range(1, num_weeks + 1):
        weeks.append({
            "week_number": w,
            "week_title": f"Week {w} — {domain}",
            "week_objective": f"Build foundational knowledge in {domain} during week {w}.",
            "what_user_should_know_after": [
                f"Core concepts from week {w}",
                "How to apply them practically",
            ],
            "status": "active" if w == 1 else "pending",
            "sections": [
                {"section_number": 1, "section_title": f"{domain} Foundations"},
                {"section_number": 2, "section_title": "Core Concepts"},
                {"section_number": 3, "section_title": "Practical Application"},
            ],
        })
    return {"weeks": weeks}


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Batch populate — generates ALL sections for ONE week in a single call
# 1 API call per week instead of 3 calls per section
# For 8 weeks: 8 total calls (well within GitHub Models 50/day limit)
# ─────────────────────────────────────────────────────────────────────────────

WEEK_BATCH_SYSTEM = """\
You are an elite curriculum architect at Wozly, a personalized AI learning platform.
You are writing content for a learner's active week. This content will be displayed directly on their dashboard.

For EACH section in the list, generate ALL of the following. Be thorough — this is what the learner reads:

1. content.explanation (REQUIRED):
   - 150–220 words minimum. NOT a definition. NOT a one-liner.
   - Explain WHY this concept exists, HOW it works, and WHERE it is used in real projects.
   - Write in second person ("You will learn...", "When you encounter...").
   - End with one practical insight or common pitfall to watch out for.

2. content.key_points (REQUIRED):
   - Exactly 4 bullet points.
   - Each is a concrete, actionable takeaway (not vague like "understand X").
   - Example: "Use const by default; only switch to let when the value must change."

3. content.code_example (REQUIRED unless the section is purely theoretical):
   - A real, runnable code snippet (15–30 lines).
   - Every non-obvious line must have an inline comment.
   - Set language to the correct programming language (javascript, python, cpp, jsx, etc).
   - Set caption to ONE sentence describing exactly what the snippet demonstrates.
   - Use null ONLY if showing code would genuinely not add value (e.g. "History of Computing").

4. resources (REQUIRED):
   - Exactly 2–3 resources.
   - Use REAL, WELL-KNOWN URLs: MDN (developer.mozilla.org), javascript.info, python.org, cppreference.com, React docs (react.dev), GeeksForGeeks, W3Schools, YouTube (Fireship, Traversy Media, The Cherno, CodeWithHarry).
   - Each resource must have a real title, real URL, correct type (documentation/article/video/tutorial), and duration_minutes (integer for videos, null otherwise).

5. practice (REQUIRED):
   - 1–2 open-ended coding tasks the learner does offline.
   - Start with "Write a program that..." or "Create a function that..." or "Build a small script that..."
   - Be specific. Bad: "Practice loops". Good: "Write a for loop that prints all prime numbers from 2 to 50."

Return ONLY a valid JSON object. No markdown fences. No explanation outside JSON. No trailing commas.

Schema (return exactly this shape):
{
  "sections": {
    "<exact section title from input>": {
      "content": {
        "explanation": "string (150-220 words)",
        "key_points": ["string", "string", "string", "string"],
        "code_example": {
          "language": "string",
          "code": "string",
          "caption": "string"
        }
      },
      "resources": [
        {
          "title": "string",
          "url": "string",
          "type": "documentation | article | video | tutorial",
          "duration_minutes": null
        }
      ],
      "practice": [
        {
          "question": "string",
          "type": "written",
          "difficulty": "easy | medium | hard"
        }
      ]
    }
  }
}
"""


async def _generate_week_batch(
    week_title: str,
    sections: list[dict],
    domain: str,
    knowledge_level: str,
) -> dict:
    """
    Generate content, resources, and practice for ALL sections in one week.
    Returns dict keyed by section_title.
    """
    section_titles = [s.get("section_title", f"Section {i+1}") for i, s in enumerate(sections)]
    sections_list = "\n".join(f"- {t}" for t in section_titles)

    user_msg = (
        f"Week Title: {week_title}\n"
        f"Domain: {domain}\n"
        f"Learner Level: {knowledge_level}\n\n"
        f"This learner is studying {domain} at the {knowledge_level} level. "
        f"This week's theme is: '{week_title}'.\n\n"
        f"Generate complete, detailed, domain-specific content for EACH of these sections:\n"
        f"{sections_list}\n\n"
        f"CRITICAL: Every explanation, code example, key point, resource URL, and practice task MUST be "
        f"specific to {domain} and directly relevant to the section title. "
        f"Do NOT write generic placeholders. "
        f"Resource URLs must be real links from MDN, official docs, YouTube, or reputable tutorials.\n"
        f"Code examples must be real, working {domain} code with inline comments.\n\n"
        f"Generate all sections now."
    )
    try:
        raw = await chat_complete(
            system=WEEK_BATCH_SYSTEM,
            user=user_msg,
            role="content",
            temperature=0.7,
            max_tokens=8000,
            json_mode=True,
        )
        result = _parse_json(raw, {})
        # Diagnostic: show what came back so we can debug key mismatches
        top = result.get("sections", result) if isinstance(result, dict) else result
        print(f"[Curator] Batch parsed top-level keys: {list(top.keys())[:8] if isinstance(top, dict) else type(top)}")
        # Handle both {"sections": {...}} and flat {title: {...}} responses
        if "sections" in result and isinstance(result["sections"], dict):
            return result["sections"]
        if isinstance(result, dict):
            return result
        return {}
    except Exception as e:
        print(f"[Curator] Batch failed for week '{week_title}': {e}")
        return {}


def _make_fallback_section(title: str, domain: str) -> dict:
    """Minimal content when batch generation fails for a section."""
    return {
        "content": {
            "explanation": (
                f"{title} is an important concept in {domain}. "
                f"Mastering it will significantly improve your ability to write effective, "
                f"production-quality code. Focus on understanding the underlying principles "
                f"before moving to more advanced applications."
            ),
            "code_example": None,
        },
        "resources": [],
        "practice": [{
            "question": f"Write a short program or explanation demonstrating your understanding of {title}.",
            "type": "written",
            "difficulty": "easy",
        }],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Master populate function — 1 API call per week, sequential across weeks
# ─────────────────────────────────────────────────────────────────────────────

async def populate_content(
    roadmap: dict,
    domain: str,
    knowledge_level: str,
    progress_cb=None,
) -> dict:
    """
    Curate content for Week 1 ONLY on initial load.

    Why: Only Week 1 is unlocked at start. Curating all weeks upfront
    wastes the daily API budget (50 req/day on GitHub Models).

    When user completes a week, the roadmap API calls populate_single_week()
    for the next week before unlocking it.

    API budget: 2 calls total (1 roadmap skeleton + 1 Week 1 curation).
    """
    weeks = roadmap.get("weeks", [])
    if not weeks:
        return roadmap

    if progress_cb:
        msg = "Curating Week 1 content..."
        if asyncio.iscoroutinefunction(progress_cb):
            await progress_cb(30, msg)
        else:
            progress_cb(30, msg)

    # Only curate the first (active) week
    week = weeks[0]
    week_title = week.get("week_title", "Week 1")
    sections = week.get("sections", [])

    print(f"[Curator] Curating Week 1: '{week_title}' ({len(sections)} sections, 1 API call)")
    batch_result = await _generate_week_batch(week_title, sections, domain, knowledge_level)

    for s_idx, section in enumerate(sections):
        title = section.get("section_title", f"Section {s_idx+1}")
        section_data = (
            batch_result.get(title)
            or next((v for k, v in batch_result.items() if title.lower() in k.lower() or k.lower() in title.lower()), None)
            or _make_fallback_section(title, domain)
        )
        weeks[0]["sections"][s_idx]["content"] = section_data.get("content", {"explanation": "", "code_example": None})
        weeks[0]["sections"][s_idx]["resources"] = section_data.get("resources", [])
        weeks[0]["sections"][s_idx]["practice"] = section_data.get("practice", [])

    if progress_cb:
        if asyncio.iscoroutinefunction(progress_cb):
            await progress_cb(100, "Week 1 is ready! Complete it to unlock Week 2.")
        else:
            progress_cb(100, "Week 1 is ready! Complete it to unlock Week 2.")

    return roadmap


async def populate_single_week(
    roadmap: dict,
    week_number: int,
    domain: str,
    knowledge_level: str,
) -> dict:
    """
    Curate content for a specific week number (1-indexed).
    Called when a user completes a week and the next one is unlocked.

    Uses 1 API call per invocation.
    """
    weeks = roadmap.get("weeks", [])
    week_idx = week_number - 1

    if week_idx < 0 or week_idx >= len(weeks):
        print(f"[Curator] Week {week_number} not found in roadmap.")
        return roadmap

    week = weeks[week_idx]
    # Check if already curated (has content)
    sections = week.get("sections", [])
    if sections and sections[0].get("content", {}).get("explanation"):
        print(f"[Curator] Week {week_number} already curated, skipping.")
        return roadmap

    week_title = week.get("week_title", f"Week {week_number}")
    print(f"[Curator] Curating Week {week_number}: '{week_title}' ({len(sections)} sections)")

    batch_result = await _generate_week_batch(week_title, sections, domain, knowledge_level)

    for s_idx, section in enumerate(sections):
        title = section.get("section_title", f"Section {s_idx+1}")
        section_data = (
            batch_result.get(title)
            or next((v for k, v in batch_result.items() if title.lower() in k.lower() or k.lower() in title.lower()), None)
            or _make_fallback_section(title, domain)
        )
        weeks[week_idx]["sections"][s_idx]["content"] = section_data.get("content", {"explanation": "", "code_example": None})
        weeks[week_idx]["sections"][s_idx]["resources"] = section_data.get("resources", [])
        weeks[week_idx]["sections"][s_idx]["practice"] = section_data.get("practice", [])

    # Unlock this week
    weeks[week_idx]["status"] = "active"
    print(f"[Curator] Week {week_number} curated and unlocked successfully.")
    return roadmap


# ─────────────────────────────────────────────────────────────────────────────
# populate_resources — backward-compat stub
# ─────────────────────────────────────────────────────────────────────────────

async def populate_resources(roadmap: dict, domain: str, knowledge_level: str, progress_cb=None) -> dict:
    """Backward-compat stub. Resources are now generated per-week in populate_content."""
    return roadmap



async def _generate_section_content(
    section_title: str, domain: str, knowledge_level: str
) -> dict:
    """Generate explanation + code_example for a single section."""
    user_msg = (
        f"Section: {section_title}\n"
        f"Domain: {domain}\n"
        f"Learner Level: {knowledge_level}"
    )
    try:
        raw = await chat_complete(
            system=SECTION_CONTENT_SYSTEM,
            user=user_msg,
            role="content",
            temperature=0.6,
            max_tokens=1200,
            json_mode=True,
        )
        result = _parse_json(raw, {})
        if result.get("explanation"):
            return result
        raise ValueError("Empty explanation")
    except Exception as e:
        print(f"[Curator] Content failed for '{section_title}': {e}")
        return {
            "explanation": (
                f"{section_title} is a key concept in {domain}. "
                f"Understanding it will help you build stronger foundations "
                f"and write more effective code."
            ),
            "code_example": None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Populate section resources
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_section_resources(
    section_title: str, domain: str, knowledge_level: str
) -> list:
    """Generate 2–3 resource links for a single section."""
    user_msg = (
        f"Section: {section_title}\n"
        f"Domain: {domain}\n"
        f"Learner Level: {knowledge_level}"
    )
    try:
        raw = await chat_complete(
            system=SECTION_RESOURCES_SYSTEM,
            user=user_msg,
            role="content",
            temperature=0.3,
            max_tokens=600,
            json_mode=True,
        )
        result = _parse_json(raw, [])
        if isinstance(result, list) and result:
            return result[:3]
        raise ValueError("Empty resources list")
    except Exception as e:
        print(f"[Curator] Resources failed for '{section_title}': {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Populate section practice questions
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_section_practice(
    section_title: str, domain: str, knowledge_level: str
) -> list:
    """Generate 1–2 practice questions for a single section."""
    user_msg = (
        f"Section: {section_title}\n"
        f"Domain: {domain}\n"
        f"Learner Level: {knowledge_level}"
    )
    try:
        raw = await chat_complete(
            system=SECTION_PRACTICE_SYSTEM,
            user=user_msg,
            role="content",
            temperature=0.5,
            max_tokens=400,
            json_mode=True,
        )
        result = _parse_json(raw, [])
        if isinstance(result, list) and result:
            return result[:2]
        raise ValueError("Empty practice list")
    except Exception as e:
        print(f"[Curator] Practice failed for '{section_title}': {e}")
        return [{
            "question": f"Practice applying {section_title} by writing a short program or explanation.",
            "type": "written",
            "difficulty": "easy"
        }]



