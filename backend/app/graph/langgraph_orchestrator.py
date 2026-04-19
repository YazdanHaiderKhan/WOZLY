"""LangGraph multi-agent orchestration graph.

Graph flow (per PRD Section 4.2):
  START → profile_node (first session) → roadmap_node → END
  Returning session → tutor_node (on-demand, no CLS mutation)
  Quiz submission → assessment_node → roadmap_node (re-plan)
  Curator sub-calls are invoked inline by roadmap_node and tutor_node.
"""
from __future__ import annotations
import asyncio
from typing import TypedDict, Literal, Optional, Any
from langgraph.graph import StateGraph, END

from app.agents import profile as profile_agent
from app.agents import roadmap as roadmap_agent
from app.agents import assessment as assessment_agent


# ─── Shared graph state ──────────────────────────────────────────────────────

class WozlyState(TypedDict):
    user_id: str
    cls: dict                          # Full CLS document
    action: Literal[
        "onboard",      # First session — run profile + roadmap
        "replan",       # Re-run roadmap after assessment
        "assess",       # Run assessment scoring + optional replan
        "tutor",        # Tutor interaction (stateless from graph POV)
    ]
    # Input payload (varies by action)
    payload: dict
    # Output accumulated by nodes
    result: dict
    error: Optional[str]


# ─── Nodes ───────────────────────────────────────────────────────────────────

async def roadmap_node(state: WozlyState) -> WozlyState:
    """Generate or re-generate the roadmap from current CLS."""
    from app.api.websocket import broadcast_event

    profile = state["cls"].get("profile", {})
    domain = profile.get("domain", "General CS")
    knowledge_level = profile.get("knowledge_level", "beginner")
    user_id = state["user_id"]

    await broadcast_event(user_id, "roadmap_progress", {
        "stage": "generating",
        "progress": 25,
        "message": f"Analyzing {domain} curriculum...",
    })

    try:
        roadmap = await roadmap_agent.generate_roadmap(state["cls"])
    except Exception as e:
        print(f"[Orchestrator] Roadmap LLM failed ({e}), using fallback.")
        roadmap = _fallback_roadmap(domain)

    state["cls"]["roadmap"] = roadmap
    state["result"]["roadmap"] = roadmap
    return state


def _fallback_roadmap(domain: str) -> dict:
    """Hardcoded demo roadmap matching the new sections schema."""
    return {
        "weeks": [
            {
                "week_number": 1,
                "week_title": f"{domain} Fundamentals",
                "week_objective": f"Understand the core foundations of {domain} and set up your development environment.",
                "what_user_should_know_after": [
                    f"What {domain} is and where it is used",
                    "How to set up your environment",
                    "Core syntax and basic constructs",
                ],
                "status": "active",
                "sections": [
                    {
                        "section_number": 1,
                        "section_title": f"Introduction to {domain}",
                        "content": {"explanation": f"{domain} is a powerful tool used across the industry.", "code_example": None},
                        "resources": [],
                        "practice": [{"question": f"Research 3 real-world applications of {domain}.", "type": "written", "difficulty": "easy"}],
                    },
                    {
                        "section_number": 2,
                        "section_title": "Environment Setup",
                        "content": {"explanation": "Setting up your tools correctly is the first step.", "code_example": None},
                        "resources": [],
                        "practice": [{"question": "Install the required tools and verify they work.", "type": "written", "difficulty": "easy"}],
                    },
                ],
            },
            {
                "week_number": 2,
                "week_title": f"Core {domain} Concepts",
                "week_objective": f"Build practical skills with the most important {domain} concepts.",
                "what_user_should_know_after": [
                    "Apply core patterns to real problems",
                    "Write clean, readable code",
                ],
                "status": "pending",
                "sections": [
                    {
                        "section_number": 1,
                        "section_title": "Core Patterns",
                        "content": {"explanation": "Core patterns form the backbone of professional code.", "code_example": None},
                        "resources": [],
                        "practice": [{"question": "Implement one core pattern from scratch.", "type": "written", "difficulty": "medium"}],
                    }
                ],
            },
        ]
    }



async def assessment_node(state: WozlyState) -> WozlyState:
    """Score quiz, update mastery, determine next action."""
    try:
        payload = state["payload"]
        questions = payload.get("questions", [])
        answers = payload.get("answers", [])

        raw_scores = await assessment_agent.score_quiz(questions, answers)
        topic_scores = assessment_agent.aggregate_topic_scores(questions, raw_scores)
        next_action = assessment_agent.determine_next_action(topic_scores)

        state["result"]["raw_scores"] = raw_scores
        state["result"]["topic_scores"] = topic_scores
        state["result"]["next_action"] = next_action
        state["action"] = "replan" if next_action in ("review", "replan") else state["action"]
    except Exception as e:
        state["error"] = f"Assessment node error: {e}"
    return state


# ─── Routing ─────────────────────────────────────────────────────────────────

def route_start(state: WozlyState) -> str:
    """Initial routing based on action type."""
    return state["action"]


def route_after_assessment(state: WozlyState) -> str:
    """After assessment: replan if needed, else end."""
    if state["result"].get("next_action") in ("review", "replan"):
        return "roadmap"
    return END


# ─── Build graph ─────────────────────────────────────────────────────────────

def build_wozly_graph():
    graph = StateGraph(WozlyState)

    # Add nodes
    graph.add_node("roadmap", roadmap_node)
    graph.add_node("assess", assessment_node)

    # Entry point routing
    graph.set_conditional_entry_point(
        route_start,
        {
            "onboard": "roadmap",
            "replan": "roadmap",
            "assess": "assess",
            "tutor": END,  # Tutor is handled outside the graph (streaming)
        },
    )

    # After roadmap → end
    graph.add_edge("roadmap", END)

    # After assessment → conditional replan or end
    graph.add_conditional_edges(
        "assess",
        route_after_assessment,
        {"roadmap": "roadmap", END: END},
    )

    return graph.compile()


# Singleton compiled graph
wozly_graph = build_wozly_graph()


async def run_graph(
    user_id: str,
    cls: dict,
    action: str,
    payload: Optional[dict] = None,
) -> dict:
    """
    Execute the LangGraph workflow.
    Returns the final result dict from the graph state.
    """
    initial_state: WozlyState = {
        "user_id": user_id,
        "cls": cls,
        "action": action,
        "payload": payload or {},
        "result": {},
        "error": None,
    }
    final_state = await wozly_graph.ainvoke(initial_state)
    if final_state.get("error"):
        raise RuntimeError(final_state["error"])
    return final_state
