"""Seed document ingestion script.

Run once: python app/rag/ingestion.py

Ingests publicly available, Creative Commons / open documentation
into the wozly_documents ChromaDB collection. Uses LangChain's
RecursiveCharacterTextSplitter (512 tokens, 64 overlap).
"""
import asyncio
import uuid
import sys
import os

# Allow running as a script from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_text_splitters import RecursiveCharacterTextSplitter
import httpx

from app.rag.embedder import embed_batch
from app.rag.chroma_client import get_collection, COLLECTION_DOCUMENTS

# ─── Seed document URLs (open / CC licensed) ──────────────────────────────────
SEED_SOURCES = [
    # Machine Learning / AI
    {
        "domain": "Machine Learning",
        "source_title": "scikit-learn User Guide",
        "url": "https://scikit-learn.org/stable/user_guide.html",
        "type": "documentation",
    },
    {
        "domain": "Machine Learning",
        "source_title": "Google ML Crash Course Glossary",
        "url": "https://developers.google.com/machine-learning/glossary",
        "type": "documentation",
    },
    # DSA
    {
        "domain": "DSA",
        "source_title": "Python Algorithm Examples — Programiz",
        "url": "https://www.programiz.com/dsa",
        "type": "article",
    },
    # Web Development
    {
        "domain": "Web Development",
        "source_title": "MDN Web Docs — HTML",
        "url": "https://developer.mozilla.org/en-US/docs/Web/HTML",
        "type": "documentation",
    },
    {
        "domain": "Web Development",
        "source_title": "MDN Web Docs — JavaScript",
        "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
        "type": "documentation",
    },
    {
        "domain": "Web Development",
        "source_title": "MDN Web Docs — CSS",
        "url": "https://developer.mozilla.org/en-US/docs/Web/CSS",
        "type": "documentation",
    },
    # Python
    {
        "domain": "Python",
        "source_title": "Python Official Tutorial",
        "url": "https://docs.python.org/3/tutorial/index.html",
        "type": "documentation",
    },
    # AI
    {
        "domain": "AI",
        "source_title": "Stanford CS229 Lecture Notes Overview",
        "url": "https://cs229.stanford.edu/main_notes.pdf",
        "type": "article",
    },
]

CHUNK_SIZE = 512      # tokens (approx chars for splitter)
CHUNK_OVERLAP = 64
BATCH_SIZE = 50


splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE * 4,      # ~4 chars per token approximation
    chunk_overlap=CHUNK_OVERLAP * 4,
    length_function=len,
)


async def fetch_text(url: str) -> str:
    """Fetch page text via HTTP. Returns empty string on failure."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "WozlyBot/1.0"})
            if resp.status_code == 200:
                # Strip heavy HTML tags (simple approach)
                text = resp.text
                import re
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text)
                return text[:50000]  # cap at 50K chars per source
    except Exception as e:
        print(f"  ⚠ Could not fetch {url}: {e}")
    return ""


async def ingest_source(source: dict, collection) -> int:
    """Ingest a single source. Returns number of chunks stored."""
    print(f"  Fetching: {source['url']}")
    text = await fetch_text(source["url"])
    if not text.strip():
        print(f"  ✗ No text retrieved for {source['source_title']}")
        return 0

    chunks = splitter.split_text(text)
    print(f"  -> {len(chunks)} chunks from {source['source_title']}")

    # Process in batches
    total = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        embeddings = await embed_batch(batch)
        ids = [str(uuid.uuid4()) for _ in batch]
        metadatas = [
            {
                "domain": source["domain"],
                "source_title": source["source_title"],
                "url": source["url"],
                "type": source["type"],
                "chunk_index": i + j,
            }
            for j in range(len(batch))
        ]
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=batch,
        )
        total += len(batch)

    return total


async def run_ingestion():
    print("WOZLY RAG Ingestion starting...")
    collection = get_collection(COLLECTION_DOCUMENTS)
    total_chunks = 0

    for source in SEED_SOURCES:
        print(f"\n[{source['domain']}] {source['source_title']}")
        n = await ingest_source(source, collection)
        total_chunks += n

    print(f"\nIngestion complete — {total_chunks} chunks stored in '{COLLECTION_DOCUMENTS}'")


if __name__ == "__main__":
    asyncio.run(run_ingestion())
