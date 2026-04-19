"""Profile Agent API router."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.deps import get_current_user_id
from app.models.schemas import (
    ProfileStartResponse, ProfileRespondRequest, ProfileRespondResponse,
    ProfileConfirmRequest, ProfileConfirmResponse,
)
from app.models.db_models import User, Session as DBSession
from app.state.cls import CLSManager
from app.agents.profile import start_profile_session, respond_to_profile, confirm_profile
from app.graph.langgraph_orchestrator import run_graph
from app.api.roadmap import background_population_task
from sqlalchemy import select

router = APIRouter(prefix="/agent/profile", tags=["profile-agent"])


@router.post("/start", response_model=ProfileStartResponse)
async def start_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Start a Profile Agent conversation session."""
    # Get user name
    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = await start_profile_session(user.name)

    # Log session start
    session = DBSession(
        id=str(uuid.uuid4()),
        user_id=str(user_id),
        agent="profile",
        started_at=datetime.utcnow(),
        messages_json=[{"role": "assistant", "content": data["first_question"]}],
    )
    db.add(session)
    await db.commit()

    return ProfileStartResponse(
        session_id=data["session_id"],
        first_question=data["first_question"],
    )


@router.post("/respond", response_model=ProfileRespondResponse)
async def respond_to_profile_endpoint(
    body: ProfileRespondRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Send a response to the Profile Agent."""
    result = await respond_to_profile(body.session_id, body.message)
    return ProfileRespondResponse(**result)


@router.post("/confirm", response_model=ProfileConfirmResponse)
async def confirm_profile_endpoint(
    body: ProfileConfirmRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Confirm the profile, save to CLS, and trigger first roadmap generation."""
    now = datetime.utcnow().isoformat()
    
    # Map explicit form fields to the CLS profile section
    profile_data = {
        "name": "Guest Student",
        "domain": body.domain or "Computer Science",
        "goal": body.goal or "General Learning",
        "duration_weeks": body.duration_weeks or 8,
        "knowledge_level": body.knowledge_level or "beginner",
        "learning_style": body.learning_style or "project-based",
        "hours_per_day": body.hours_per_day or 2,
        "prior_knowledge": [],
        "created_at": now,
    }

    # Write profile to CLS
    def _patch_profile(cls: dict) -> dict:
        cls["profile"] = profile_data
        return cls

    await CLSManager.update_state(user_id, db, _patch_profile)

    from app.api.websocket import broadcast_event
    await broadcast_event(user_id, "roadmap_progress", {
        "stage": "start",
        "progress": 5,
        "message": "Starting roadmap generation",
    })

    # Run LangGraph to generate first roadmap
    cls = await CLSManager.get_state(user_id, db)
    final_state = await run_graph(user_id, cls, action="onboard")

    await broadcast_event(user_id, "roadmap_progress", {
        "stage": "generated",
        "progress": 80,
        "message": "Roadmap generated, preparing resources",
    })

    # Save roadmap back to CLS
    roadmap = final_state["result"].get("roadmap", {})

    def _patch_roadmap(c: dict) -> dict:
        c["roadmap"] = roadmap
        return c

    updated_cls = await CLSManager.update_state(user_id, db, _patch_roadmap)

    # Start the heavy lifters in the background for initial onboarding
    background_tasks.add_task(background_population_task, user_id, get_db)

    await broadcast_event(user_id, "roadmap_progress", {
        "stage": "saved",
        "progress": 95,
        "message": "Saving structure, hydrating resources in background",
    })

    # Notify WebSocket subscribers
    await broadcast_event(user_id, "roadmap_updated", {"roadmap": roadmap})
    await broadcast_event(user_id, "roadmap_progress", {
        "stage": "done",
        "progress": 100,
        "message": "Roadmap ready",
    })

    return ProfileConfirmResponse(cls_snapshot=updated_cls)

@router.delete("/reset")
async def reset_profile_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Wipes the user's roadmap and mastery, used for restarting the presentation demo."""
    def _wipe_cls(cls: dict) -> dict:
        cls["profile"] = None
        cls["roadmap"] = None
        cls["mastery"] = {}
        return cls

    await CLSManager.update_state(user_id, db, _wipe_cls)
    return {"status": "ok", "message": "Demo reset successfully"}
