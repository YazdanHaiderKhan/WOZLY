"""FastAPI application entrypoint — no-Docker version.
Tables are created automatically on startup (SQLite).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.database import init_db
from app.api import auth, profile, roadmap, tutor, assessment, websocket, user

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create SQLite tables on every startup
    await init_db()
    print("Database ready")

    # Inject Guest user to bypass auth completely
    from app.db.database import AsyncSessionLocal
    from app.models.db_models import User, LearnerState
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        guest_id_str = "00000000-0000-0000-0000-000000000000"
        res = await db.execute(select(User).where(User.id == guest_id_str))
        if not res.scalar_one_or_none():
            guest_user = User(
                id=guest_id_str, email="guest@wozly.local", hashed_password="guest", name="Guest Student"
            )
            guest_cls = LearnerState(
                user_id=guest_id_str,
                cls_json={"profile": None, "roadmap": None, "mastery": {}, "session_history": [], "hint_count": 0, "quizzes_taken": 0},
                version=0
            )
            db.add(guest_user)
            db.add(guest_cls)
            await db.commit()

    # Verify ChromaDB local client
    try:
        from app.rag.chroma_client import get_chroma_client
        get_chroma_client()
        print("ChromaDB local store ready")
    except Exception as e:
        print(f"ChromaDB error: {e}")

    yield


app = FastAPI(
    title="Wozly API",
    description="AI-Driven Multi-Agent Personalized Learning Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(roadmap.router)
app.include_router(tutor.router)
app.include_router(assessment.router)
app.include_router(websocket.router)
app.include_router(user.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}
