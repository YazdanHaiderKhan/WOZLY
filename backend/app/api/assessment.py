"""Assessment Agent API router — quiz generation and submission."""
import uuid
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.core.deps import get_current_user_id
from app.models.schemas import (
    AssessmentGenerateRequest, AssessmentGenerateResponse,
    AssessmentSubmitRequest, AssessmentSubmitResponse,
    QuestionSchema, MasteryDelta,
)
from app.models.db_models import Quiz
from app.state.cls import CLSManager, compute_ema
from app.agents.assessment import generate_quiz, score_quiz, aggregate_topic_scores, determine_next_action
from app.graph.langgraph_orchestrator import run_graph
from app.api.websocket import broadcast_event
from app.api.roadmap import background_unlock_week

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.post("/generate", response_model=AssessmentGenerateResponse)
async def generate_assessment(
    body: AssessmentGenerateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate a fresh quiz for the given week."""
    if body.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    cls = await CLSManager.get_state(body.user_id, db)
    profile = cls.get("profile", {})
    if not profile:
        raise HTTPException(status_code=400, detail="Complete onboarding before taking a quiz")

    roadmap = cls.get("roadmap", {})
    weeks = roadmap.get("weeks", [])
    week_data = next((w for w in weeks if w.get("week_number") == body.week_number), None)
    if not week_data:
        raise HTTPException(status_code=404, detail=f"Week {body.week_number} not found in roadmap")

    # Support both old schema (topics list) and new schema (sections list)
    topics = week_data.get("topics") or []
    if not topics:
        # New schema: extract section titles as topic names
        sections = week_data.get("sections", [])
        topics = [
            s.get("section_title", f"Section {s.get('section_number', i+1)}")
            for i, s in enumerate(sections)
        ]
    if not topics:
        topics = [week_data.get("week_title", f"Week {body.week_number} Content")]

    questions = await generate_quiz(
        topics=topics,
        knowledge_level=profile.get("knowledge_level", "beginner"),
        domain=profile.get("domain", ""),
        week_number=body.week_number,
    )

    # Persist quiz (include correct_answer for scoring later)
    quiz_id = str(uuid.uuid4())
    quiz_row = Quiz(
        id=quiz_id,
        user_id=str(body.user_id),
        week_number=body.week_number,
        questions_json=questions,
        submitted_at=None,
        scores_json=None,
    )
    db.add(quiz_row)
    await db.commit()

    # Return questions WITH correct_answer for immediate feedback in the UI
    client_questions = []
    for q in questions:
        cq = QuestionSchema(
            id=q["id"],
            type=q["type"],
            question=q["question"],
            options=q.get("options"),
            correct_answer=q.get("correct_answer"),
        )
        client_questions.append(cq)

    return AssessmentGenerateResponse(quiz_id=str(quiz_id), questions=client_questions)


@router.post("/submit", response_model=AssessmentSubmitResponse)
async def submit_assessment(
    body: AssessmentSubmitRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Submit quiz answers, update mastery, trigger re-plan if needed."""
    result = await db.execute(select(Quiz).where(Quiz.id == str(body.quiz_id)))
    quiz_row = result.scalar_one_or_none()
    if not quiz_row:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if str(quiz_row.user_id) != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if quiz_row.submitted_at:
        raise HTTPException(status_code=400, detail="Quiz already submitted")

    questions = quiz_row.questions_json
    raw_scores = await score_quiz(questions, [a.model_dump() for a in body.answers])
    topic_scores = aggregate_topic_scores(questions, raw_scores)
    next_action = determine_next_action(topic_scores)

    # Mark quiz as submitted
    quiz_row.submitted_at = datetime.utcnow()
    quiz_row.scores_json = raw_scores
    await db.commit()

    # Update mastery via EMA for each topic
    cls = await CLSManager.get_state(user_id, db)
    mastery_deltas: list[MasteryDelta] = []

    for topic, observed in topic_scores.items():
        prev = cls.get("mastery", {}).get(topic, {}).get("current_score", 0.0)
        await CLSManager.apply_quiz_score(user_id, db, topic, observed)
        new_cls = await CLSManager.get_state(user_id, db)
        new_score = new_cls.get("mastery", {}).get(topic, {}).get("current_score", observed)

        # Determine action label
        if new_score >= 0.8:
            action_label = "mastered"
        elif new_score >= 0.6:
            action_label = "continue"
        else:
            action_label = "review_inserted"

        mastery_deltas.append(MasteryDelta(
            topic=topic,
            previous_score=prev,
            new_score=new_score,
            action=action_label,
        ))

    # Increment quizzes_taken
    def _inc_quizzes(c: dict) -> dict:
        c["quizzes_taken"] = c.get("quizzes_taken", 0) + 1
        return c
    await CLSManager.update_state(user_id, db, _inc_quizzes)

    # Trigger re-plan via LangGraph if needed
    if next_action in ("review", "replan"):
        # User failed the assessment — keep the existing roadmap intact.
        # They stay on the current week and can retake the quiz.
        # We intentionally do NOT replan here to preserve curated content.
        print(f"[Assessment] User {user_id} scored below threshold (action={next_action}). Keeping existing roadmap.")
        await broadcast_event(user_id, "mastery_updated", {"topic_scores": topic_scores})

    else:
        # If action is 'continue', the user passed! Advance the roadmap.
        cls = await CLSManager.get_state(user_id, db)
        roadmap = cls.get("roadmap", {})
        weeks = roadmap.get("weeks", [])
        
        # Find active week, mark complete, mark next as active
        advanced = False
        for i, w in enumerate(weeks):
            if w.get("status") == "active":
                w["status"] = "complete"
                if i + 1 < len(weeks):
                    weeks[i + 1]["status"] = "active"
                advanced = True
                break
                
        if advanced:
            next_week_num = None
            for w in weeks:
                if w.get("status") == "active":
                    next_week_num = w.get("week_number")
                    break
            def _patch_roadmap(c: dict) -> dict:
                c["roadmap"] = roadmap
                return c
            await CLSManager.update_state(user_id, db, _patch_roadmap)
            await broadcast_event(user_id, "roadmap_updated", {"roadmap": roadmap})
            # Curate the next week's content in the background (same as complete-week endpoint)
            if next_week_num:
                background_tasks.add_task(background_unlock_week, user_id, next_week_num, get_db)
                print(f"[Assessment] Triggered Week {next_week_num} curation for user {user_id}")

    await broadcast_event(user_id, "mastery_updated", {"topic_scores": topic_scores})

    return AssessmentSubmitResponse(
        scores={q["id"]: raw_scores.get(q["id"], 0.0) for q in questions},
        mastery_delta=mastery_deltas,
        next_action=next_action,
    )
