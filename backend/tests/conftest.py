"""pytest fixtures for WOZLY backend tests."""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.db.database import Base, get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_wozly.db"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db):
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_cls():
    return {
        "user_id": "test-user-123",
        "profile": {
            "name": "Test User",
            "domain": "Machine Learning",
            "goal": "Understand neural networks",
            "duration_weeks": 6,
            "knowledge_level": "beginner",
            "prior_knowledge": ["Python", "NumPy"],
            "created_at": "2026-01-01T00:00:00",
        },
        "roadmap": {"weeks": []},
        "mastery": {},
        "session_history": [],
        "hint_count": 0,
        "quizzes_taken": 0,
    }
