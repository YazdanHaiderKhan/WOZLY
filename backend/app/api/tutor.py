"""Tutor Agent API router — streaming SSE + regular chat."""
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.deps import get_current_user_id
from app.models.schemas import TutorChatRequest, TutorChatResponse
from app.state.cls import CLSManager
from app.agents.tutor import handle_tutor_chat, stream_hint
from app.agents.curator import curate_single_topic

router = APIRouter(prefix="/agent/tutor", tags=["tutor-agent"])


@router.post("/chat", response_model=TutorChatResponse)
async def tutor_chat(
    body: TutorChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming tutor hint endpoint."""
    cls = await CLSManager.get_state(body.user_id, db)
    result = await handle_tutor_chat(
        user_id=body.user_id,
        topic_id=body.topic_id,
        user_message=body.message,
        history=body.history,
        cls=cls,
    )

    # Update CLS hint_count and session history
    await CLSManager.increment_hint_count(body.user_id, db, body.topic_id)
    await CLSManager.append_session_history(
        body.user_id, db, "tutor", body.message, result["hint"]
    )

    return TutorChatResponse(**result)


@router.post("/chat/stream")
async def tutor_chat_stream(
    body: TutorChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming tutor hint — yields tokens progressively."""
    cls = await CLSManager.get_state(body.user_id, db)
    domain = cls.get("profile", {}).get("domain", "")
    knowledge_level = cls.get("profile", {}).get("knowledge_level", "beginner")
    hint_count = cls.get("hint_count", 0)

    resources = await curate_single_topic(body.topic_id, knowledge_level, domain)

    async def event_generator():
        # SSE metadata header
        yield f"data: {json.dumps({'type': 'start', 'hint_count': hint_count + 1})}\n\n"

        full_hint = ""
        async for token in stream_hint(
            user_message=body.message,
            topic_id=body.topic_id,
            hint_count=hint_count,
            history=body.history,
            resources=resources,
        ):
            full_hint += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # Update CLS after streaming completes
        await CLSManager.increment_hint_count(body.user_id, db, body.topic_id)
        await CLSManager.append_session_history(
            body.user_id, db, "tutor", body.message, full_hint
        )

        resources_payload = [
            {"title": r.get("title"), "url": r.get("url"), "type": r.get("type")}
            for r in resources
        ]
        yield f"data: {json.dumps({'type': 'done', 'resources': resources_payload, 'hint_count': hint_count + 1})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
