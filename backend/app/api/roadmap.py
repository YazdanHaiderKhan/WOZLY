"""Roadmap API router."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.deps import get_current_user_id
from app.models.schemas import RoadmapGenerateRequest
from app.state.cls import CLSManager
from app.graph.langgraph_orchestrator import run_graph
from app.api.websocket import broadcast_event
from app.agents import roadmap as roadmap_agent

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


# ─────────────────────────────────────────────────────────────────────────────
# Background tasks
# ─────────────────────────────────────────────────────────────────────────────

async def background_population_task(user_id: str, db_factory):
    """Curate ONLY Week 1 content right after roadmap generation. 1 API call."""
    print(f"[Background] Starting Week 1 curation for user {user_id}")
    try:
        async for db in db_factory():
            cls = await CLSManager.get_state(user_id, db)
            roadmap = cls.get("roadmap", {})
            profile = cls.get("profile", {})
            domain = profile.get("domain", "General CS")
            knowledge_level = profile.get("knowledge_level", "beginner")

            async def _cb(p, m):
                await broadcast_event(user_id, "roadmap_progress", {
                    "stage": "content", "progress": p, "message": m
                })

            roadmap = await roadmap_agent.populate_content(roadmap, domain, knowledge_level, progress_cb=_cb)

            def _patch(c: dict) -> dict:
                c["roadmap"] = roadmap
                return c

            await CLSManager.update_state(user_id, db, _patch)
            await broadcast_event(user_id, "roadmap_updated", {"roadmap": roadmap})
            await broadcast_event(user_id, "roadmap_progress", {
                "stage": "done", "progress": 100,
                "message": "Week 1 is ready! Complete it to unlock Week 2."
            })
            print(f"[Background] Week 1 curation done for user {user_id}")
            break
    except Exception as e:
        print(f"[Background] FATAL ERROR in population task: {e}")
        import traceback
        traceback.print_exc()


async def background_unlock_week(user_id: str, week_number: int, db_factory):
    """Curate and unlock a specific week when user completes the previous one."""
    print(f"[Background] Curating Week {week_number} for user {user_id}")
    try:
        async for db in db_factory():
            cls = await CLSManager.get_state(user_id, db)
            roadmap = cls.get("roadmap", {})
            profile = cls.get("profile", {})
            domain = profile.get("domain", "General CS")
            knowledge_level = profile.get("knowledge_level", "beginner")

            await broadcast_event(user_id, "roadmap_progress", {
                "stage": "unlocking",
                "progress": 10,
                "message": f"Preparing Week {week_number} content...",
            })

            roadmap = await roadmap_agent.populate_single_week(
                roadmap, week_number, domain, knowledge_level
            )

            def _patch(c: dict) -> dict:
                c["roadmap"] = roadmap
                return c

            await CLSManager.update_state(user_id, db, _patch)
            await broadcast_event(user_id, "roadmap_updated", {"roadmap": roadmap})
            await broadcast_event(user_id, "roadmap_progress", {
                "stage": "done", "progress": 100,
                "message": f"Week {week_number} is now unlocked!",
            })
            print(f"[Background] Week {week_number} ready for user {user_id}")
            break
    except Exception as e:
        print(f"[Background] ERROR unlocking week {week_number}: {e}")
        import traceback
        traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=dict)
async def get_roadmap(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the current roadmap and mastery snapshot for a user."""
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    cls = await CLSManager.get_state(user_id, db)
    return {
        "roadmap": cls.get("roadmap", {"weeks": []}),
        "mastery_snapshot": cls.get("mastery", {}),
    }


@router.post("/{user_id}/complete-week", response_model=dict)
async def complete_week(
    user_id: str,
    body: dict,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a week as complete and trigger background curation for the next week.
    Body: { "completed_week_number": 1 }
    """
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    completed_week = body.get("completed_week_number", 1)
    next_week = completed_week + 1

    def _mark_complete(c: dict) -> dict:
        for week in c.get("roadmap", {}).get("weeks", []):
            if week.get("week_number") == completed_week:
                week["status"] = "complete"
        return c

    updated_cls = await CLSManager.update_state(user_id, db, _mark_complete)
    total_weeks = len(updated_cls.get("roadmap", {}).get("weeks", []))

    if next_week <= total_weeks:
        background_tasks.add_task(background_unlock_week, user_id, next_week, get_db)
        return {
            "status": "ok",
            "completed_week": completed_week,
            "next_week_unlocking": next_week,
        }

    return {"status": "ok", "completed_week": completed_week, "message": "Course complete!"}


@router.post("/generate", response_model=dict)
async def generate_roadmap(
    body: RoadmapGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full roadmap re-plan."""
    if body.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    cls = await CLSManager.get_state(body.user_id, db)
    if not cls.get("profile"):
        raise HTTPException(status_code=400, detail="Profile not set. Complete onboarding first.")

    await broadcast_event(body.user_id, "roadmap_progress", {
        "stage": "start", "progress": 5,
        "message": "Analyzing curriculum structure...",
    })

    # Step 1: Generate skeleton (1 API call — fast)
    final_state = await run_graph(body.user_id, cls, action="replan")
    roadmap = final_state["result"].get("roadmap", {})

    def _patch(c: dict) -> dict:
        c["roadmap"] = roadmap
        return c

    updated_cls = await CLSManager.update_state(body.user_id, db, _patch)
    await broadcast_event(body.user_id, "roadmap_updated", {"roadmap": roadmap})

    # Step 2: Curate Week 1 in background (1 API call)
    background_tasks.add_task(background_population_task, body.user_id, get_db)

    return {"roadmap": roadmap, "mastery_snapshot": updated_cls.get("mastery", {})}
