from __future__ import annotations
import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, field_validator


# ─────────────────────────────────── Auth ────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ──────────────────────────────── CLS Sub-schemas ────────────────────────────

class ResourceSchema(BaseModel):
    title: str
    url: str
    type: Literal["video", "article", "documentation", "exercise"]
    relevance_score: Optional[float] = None

class TopicSchema(BaseModel):
    name: str
    overview: str
    key_points: list[str]
    example_code: str

class RoadmapWeekSchema(BaseModel):
    week_number: int
    topics: list[TopicSchema]
    status: Literal["pending", "active", "complete"]
    resources: list[ResourceSchema] = []
    practice_project: Optional[str] = None

class MasteryHistoryItem(BaseModel):
    score: float
    timestamp: datetime

class MasteryTopicSchema(BaseModel):
    current_score: float        # 0.0–1.0 EMA value
    history: list[MasteryHistoryItem] = []
    next_review: Optional[datetime] = None

class ProfileSchema(BaseModel):
    name: str
    domain: str
    goal: str
    duration_weeks: int
    knowledge_level: Literal["beginner", "intermediate", "advanced"]
    prior_knowledge: list[str] = []
    created_at: datetime

class SessionHistoryItem(BaseModel):
    session_id: str
    agent: str
    input: str
    output: str
    timestamp: datetime


# ──────────────────────────────── Full CLS ────────────────────────────────────

class CLSSchema(BaseModel):
    user_id: str
    profile: Optional[ProfileSchema] = None
    roadmap: Optional[dict] = None          # {"weeks": [RoadmapWeekSchema]}
    mastery: dict[str, MasteryTopicSchema] = {}
    session_history: list[SessionHistoryItem] = []
    hint_count: int = 0
    quizzes_taken: int = 0


# ──────────────────────────────── Profile Agent ───────────────────────────────

class ProfileStartResponse(BaseModel):
    session_id: str
    first_question: str

class ProfileRespondRequest(BaseModel):
    session_id: str
    message: str

class ProfileRespondResponse(BaseModel):
    next_question: Optional[str] = None
    profile_summary: Optional[str] = None
    is_complete: bool = False

class ProfileConfirmRequest(BaseModel):
    session_id: Optional[str] = None
    confirmed: bool = True
    domain: Optional[str] = None
    goal: Optional[str] = None
    duration_weeks: Optional[int] = 8
    knowledge_level: Optional[Literal["beginner", "intermediate", "advanced"]] = "beginner"
    learning_style: Optional[str] = "project-based"
    hours_per_day: Optional[int] = 2

class ProfileConfirmResponse(BaseModel):
    cls_snapshot: dict


# ──────────────────────────────── Roadmap ────────────────────────────────────

class RoadmapResponse(BaseModel):
    roadmap: list[RoadmapWeekSchema]
    mastery_snapshot: dict[str, MasteryTopicSchema]

class RoadmapGenerateRequest(BaseModel):
    user_id: str


# ──────────────────────────────── Tutor ──────────────────────────────────────

class TutorChatRequest(BaseModel):
    user_id: str
    topic_id: str
    message: str
    history: list[dict] = []

class TutorChatResponse(BaseModel):
    hint: str
    resources: list[ResourceSchema]
    hint_count: int
    hint_level: int   # 1-4


# ──────────────────────────────── Assessment ──────────────────────────────────

class QuestionSchema(BaseModel):
    id: str
    type: Literal["multiple_choice", "short_answer", "applied"]
    question: str
    options: Optional[list[str]] = None    # MC only
    correct_answer: Optional[str] = None   # omitted in response to client

class AssessmentGenerateRequest(BaseModel):
    user_id: str
    week_number: int

class AssessmentGenerateResponse(BaseModel):
    quiz_id: str
    questions: list[QuestionSchema]

class AnswerSchema(BaseModel):
    question_id: str
    answer: str

class AssessmentSubmitRequest(BaseModel):
    quiz_id: str
    answers: list[AnswerSchema]

class MasteryDelta(BaseModel):
    topic: str
    previous_score: float
    new_score: float
    action: str   # "mastered" | "continue" | "review_inserted"

class AssessmentSubmitResponse(BaseModel):
    scores: dict[str, float]
    mastery_delta: list[MasteryDelta]
    next_action: Literal["continue", "review", "replan"]


# ──────────────────────────────── WebSocket Events ───────────────────────────

class WSEvent(BaseModel):
    type: Literal["roadmap_updated", "mastery_updated", "quiz_ready"]
    payload: dict
