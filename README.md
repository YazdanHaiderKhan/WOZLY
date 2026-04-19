# WOZLY — AI-Driven Multi-Agent Personalized Learning Platform

> Orchestrating five specialized LLM agents (Profile · Roadmap · Curator · Tutor · Assessment) via LangGraph to deliver real-time, adaptive personalized learning roadmaps.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  React 18 + TypeScript + Tailwind  (port 3000)                      │
│  Dashboard · Onboarding Chat · Quiz · Profile                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP / WebSocket
┌────────────────────────────▼────────────────────────────────────────┐
│  FastAPI + Uvicorn  (port 8000)                                     │
│  /auth  /agent/profile  /agent/tutor  /roadmap  /assessment  /ws    │
└──────┬──────────────────────────────────────────────────────────────┘
       │ LangGraph StateGraph
┌──────▼──────────────────────────────────────────────────────────────┐
│  Agent Layer                                                        │
│  ProfileAgent → RoadmapAgent ↔ CuratorAgent                        │
│  TutorAgent (streaming SSE)                                         │
│  AssessmentAgent → (triggers RoadmapAgent re-plan)                 │
└──────┬─────────────────────────────┬───────────────────────────────┘
       │ SQLAlchemy + asyncpg        │ chromadb-client
┌──────▼──────────┐         ┌────────▼────────────────────────────────┐
│  PostgreSQL 16  │         │  ChromaDB                               │
│  users          │         │  wozly_documents (seed corpus)          │
│  learner_states │         │  wozly_web_cache (Tavily fallback)      │
│  sessions       │         └─────────────────────────────────────────┘
│  quizzes        │
│  resources      │
└─────────────────┘
```

## Quick Start

### Prerequisites
- Docker Desktop ≥ 4.x
- OpenAI API key
- Tavily API key (free tier works)

### 1 — Clone & configure
```bash
git clone <repo-url>
cd wozly
cp .env.example .env
# Edit .env — fill in OPENAI_API_KEY, TAVILY_API_KEY, JWT_SECRET
```

### 2 — Start all services
```bash
docker-compose up --build
```

This starts: PostgreSQL → ChromaDB → FastAPI backend (runs Alembic migrations) → React frontend.

### 3 — Seed the RAG corpus
```bash
docker exec wozly_backend python app/rag/ingestion.py
```

### 4 — Open the app
- Frontend: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs
- ChromaDB UI: http://localhost:8001

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | — |
| `TAVILY_API_KEY` | Tavily web search key | — |
| `DATABASE_URL` | Async PostgreSQL URL | See `.env.example` |
| `CHROMA_HOST/PORT` | ChromaDB connection | `localhost:8001` |
| `JWT_SECRET` | JWT signing secret | **must change** |
| `ALPHA` | EMA learning rate | `0.3` |
| `MAX_HINTS_PER_TOPIC` | Tutor hint ceiling | `5` |
| `RAG_TOP_K` | ChromaDB retrieval count | `5` |

## Project Structure

```
wozly/
├── backend/
│   ├── app/
│   │   ├── agents/          # profile, roadmap, curator, tutor, assessment
│   │   ├── api/             # FastAPI routers
│   │   ├── core/            # config, security
│   │   ├── db/              # database session
│   │   ├── graph/           # LangGraph orchestrator
│   │   ├── models/          # Pydantic schemas + SQLAlchemy ORM
│   │   ├── rag/             # ChromaDB client, embedder, ingestion, retriever
│   │   ├── state/           # CLS manager (EMA, spaced repetition)
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/             # Axios client wrappers
│   │   ├── components/      # RoadmapPanel, MasteryChart, TutorChat, ProgressRing
│   │   ├── hooks/           # useAuth, useCLS, useWebSocket
│   │   └── pages/           # Register, Login, Onboarding, Dashboard, Quiz, Profile
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## Research Paper
Based on: *Wozly: AI-Driven Multi-Agent System for Personalized Learning Roadmaps*
Khan, Sharma, Goyal, Kwatra — Bharati Vidyapeeth's College of Engineering, New Delhi
