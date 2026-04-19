"""Text embedding — supports GitHub Models + local fallback for Groq/Gemini."""
import asyncio
import threading
from app.core.config import get_settings

_settings = get_settings()

_local_model = None
_local_model_lock = threading.Lock()


def _get_local_model():
    """Lazy-load and cache the sentence-transformers model."""
    global _local_model
    if _local_model is None:
        with _local_model_lock:
            if _local_model is None:
                from sentence_transformers import SentenceTransformer
                _local_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _local_model


async def _embed_openai_compatible(texts: list[str]) -> list[list[float]]:
    """Embed using OpenAI-compatible API (GitHub Models or OpenAI)."""
    from app.core.llm_client import get_llm_client
    client = get_llm_client()
    try:
        response = await client.embeddings.create(
            model=_settings.openai_embedding_model,
            input=[t.replace("\n", " ") for t in texts],
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        print(f"  Fallback to local embeddings due to API error: {e}")
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: _embed_local_sync(texts))


async def _embed_local(texts: list[str]) -> list[list[float]]:
    """Local sentence-transformers fallback for Groq/Gemini providers."""
    try:
        model = _get_local_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    except ImportError:
        raise RuntimeError(
            "sentence-transformers not installed. "
            "Run: pip install sentence-transformers\n"
            "Or switch LLM_PROVIDER=github to use GitHub Models embeddings."
        )


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings using the configured provider."""
    if _settings.llm_provider in ("github", "openai"):
        return await _embed_openai_compatible(texts)
    else:
        # Groq/Gemini don't have embedding APIs — use local model
        return await asyncio.get_event_loop().run_in_executor(None, lambda: _embed_local_sync(texts))


def _embed_local_sync(texts: list[str]) -> list[list[float]]:
    """Sync wrapper for local embedding (runs in thread pool)."""
    try:
        model = _get_local_model()
        return model.encode(texts, convert_to_numpy=True).tolist()
    except (ImportError, ModuleNotFoundError):
        print("[Embedder] sentence-transformers not installed. Skipping local RAG and using Tavily fallback.")
        # Return dummy embeddings so ChromaDB can fail gracefully and Tavily can take over
        return [[0.0] * 384 for _ in texts]


async def embed_text(text: str) -> list[float]:
    """Embed a single string."""
    results = await embed_batch([text])
    return results[0]
