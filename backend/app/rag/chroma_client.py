"""Local ChromaDB persistent client — no server needed."""
from __future__ import annotations
import chromadb
from app.core.config import get_settings
from typing import Optional

_settings = get_settings()

_client: Optional[chromadb.PersistentClient] = None

COLLECTION_DOCUMENTS = "wozly_documents"
COLLECTION_WEB_CACHE = "wozly_web_cache"


def get_chroma_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=_settings.chroma_persist_dir)
    return _client


def get_collection(name: str):
    """Sync collection accessor for local ChromaDB."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
