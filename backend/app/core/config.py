from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal
from pathlib import Path
import os

# Locate .env: check current dir first, then parent (project root)
_env_file = ".env"
if not Path(".env").exists() and Path("../.env").exists():
    _env_file = "../.env"


class Settings(BaseSettings):
    # ── LLM Provider ──────────────────────────────────────────────────────────
    # Default provider
    llm_provider: Literal["github", "groq", "openai", "gemini", "openrouter", "sambanova"] = "github"


    # GitHub Models (FREE — uses your GitHub PAT)
    # Get token: github.com → Settings → Developer Settings → Personal Access Tokens
    github_token: str = ""
    github_models_base_url: str = "https://models.inference.ai.azure.com"

    # Model names (GitHub Models identifiers)
    openai_model_tutor: str = "gpt-4o"
    openai_model_roadmap: str = "gpt-4o"
    openai_model_profile: str = "gpt-4o-mini"
    openai_model_assessment: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # OpenAI (if you ever get a paid key)
    openai_api_key: str = ""

    # Groq (FREE — groq.com, supports Llama 3 / Mixtral)
    groq_api_key: str = ""
    groq_model_tutor: str = "llama3-70b-8192"
    groq_model_fast: str = "llama3-8b-8192"

    # Google Gemini (FREE tier — aistudio.google.com)
    gemini_api_key: str = ""
    gemini_model_tutor: str = "gemini-2.5-pro"
    gemini_model_fast: str = "gemini-2.5-flash"
    
    # OpenRouter (openrouter.ai)
    openrouter_api_key: str = ""
    openrouter_model_tutor: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_model_fast: str = "google/gemma-4-26b-a4b-it:free"

    # SambaNova (Dedicated Agent Keys)
    sambanova_roadmap_api_key: str = ""
    sambanova_roadmap_model: str = "DeepSeek-V3.1"
    
    sambanova_content_api_key: str = ""
    sambanova_content_model: str = "DeepSeek-V3.1"
    
    sambanova_tutor_api_key: str = ""
    sambanova_tutor_model: str = "DeepSeek-V3.1"
    
    sambanova_assessment_api_key: str = ""
    sambanova_assessment_model: str = "DeepSeek-V3.1"

    @property
    def clean_gemini_tutor(self):
        val = self.gemini_model_tutor.replace("-latest", "")
        return val.replace("1.5", "2.5")
        
    @property
    def clean_gemini_fast(self):
        val = self.gemini_model_fast.replace("-latest", "")
        return val.replace("1.5", "2.5")

    # ── Web Search Fallback ───────────────────────────────────────────────────
    tavily_api_key: str = ""

    # ── Database (SQLite by default — no install needed) ────────────────────────
    database_url: str = "sqlite+aiosqlite:///./wozly.db"
    postgres_user: str = "wozly"
    postgres_password: str = "wozlypass"
    postgres_db: str = "wozlydb"

    # ── ChromaDB (local persistent folder — no server needed) ─────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_persist_dir: str = "./chroma_data"

    # ── Auth ──────────────────────────────────────────────────────────────────
    jwt_secret: str = "change-me-to-a-long-random-secret-minimum-32-chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ── Agent Tuning ──────────────────────────────────────────────────────────
    alpha: float = 0.3
    max_hints_per_topic: int = 5
    rag_top_k: int = 5
    rag_min_confidence: float = 0.7

    # ── Roadmap Generation ───────────────────────────────────────────────────
    roadmap_fallback_demo: bool = False

    # ── LLM Retry / Rate Limit Handling ───────────────────────────────────────
    llm_retry_on_rate_limit: bool = True
    llm_retry_max_attempts: int = 3
    llm_retry_base_delay: float = 1.5
    llm_retry_max_delay: float = 8.0

    class Config:
        env_file = _env_file
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
