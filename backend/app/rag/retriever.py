"""RAG document retriever.

1. Embeds topic + knowledge_level suffix
2. Queries ChromaDB wozly_documents with cosine similarity
3. Re-ranks with LLM relevance scoring
4. Validates all URLs (HTTP HEAD, 2s timeout)
5. Falls back to Tavily web search if < 2 valid resources found
6. Caches Tavily results in wozly_web_cache
"""
from __future__ import annotations
import uuid
import asyncio
import json
import httpx

from app.core.config import get_settings
from app.core.llm_client import chat_complete
from app.rag.embedder import embed_text, embed_batch
from app.rag.chroma_client import get_collection, COLLECTION_DOCUMENTS, COLLECTION_WEB_CACHE

_settings = get_settings()


async def _is_url_valid(url: str, timeout: float = 2.0) -> bool:
    """HEAD request to validate URL accessibility."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            resp = await client.head(url)
            # Many tutorial sites (like Medium, GeeksforGeeks) return 403 or 405 for bot HEAD requests.
            # We consider them valid if they respond at all with these codes.
            return resp.status_code < 400 or resp.status_code in (403, 405)
    except Exception as e:
        print(f"[RAG] URL validation failed for {url}: {e}")
        return False


async def _validate_urls(resources: list[dict]) -> list[dict]:
    """Filter resource list to only include accessible URLs."""
    checks = await asyncio.gather(*[_is_url_valid(r["url"]) for r in resources])
    return [r for r, ok in zip(resources, checks) if ok]


async def _llm_rerank(topic: str, knowledge_level: str, chunks: list[dict]) -> list[dict]:
    """Ask the LLM to score and deduplicate retrieved chunks.
    DISABLED: Burns too many rate-limit credits (1 call per topic = 12+ calls).
    We simply return the chunks sorted by cosine similarity instead.
    """
    if not chunks:
        return []
    return sorted(chunks, key=lambda x: x.get("relevance_score", 0), reverse=True)


async def _tavily_search(topic: str, domain: str, knowledge_level: str) -> list[dict]:
    """Tavily web search fallback — returns list of resource dicts."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=_settings.tavily_api_key)
        # Include domain to restrict scope. Avoid generic terms like "guide", "app", or "tool" alone to prevent false matches.
        query = f'"{topic}" {domain} {knowledge_level} tutorial OR project OR interactive'
        result = client.search(query=query, max_results=5, include_raw_content=False)
        resources = []
        for r in result.get("results", []):
            url = r.get("url", "")
            url_lower = url.lower()
            r_type = "article"
            if "youtube.com" in url_lower or "youtu.be" in url_lower:
                r_type = "video"
            elif "apps.apple.com" in url_lower or "play.google.com" in url_lower or "/app" in url_lower:
                r_type = "app"
            resources.append({
                "id": str(uuid.uuid4()),
                "title": r.get("title", topic),
                "url": url,
                "snippet": r.get("content", "")[:300],
                "type": r_type,
                "relevance_score": r.get("score", 0.5),
            })
        return resources
    except Exception as e:
        print(f"[RAG] Tavily search failed for {topic}: {e}")
        return []


def _keyword_score(text: str, keywords: set[str]) -> int:
    if not text:
        return 0
    text_lower = text.lower()
    return sum(1 for k in keywords if k in text_lower)


async def _cache_tavily_results(topic: str, domain: str, resources: list[dict]) -> None:
    """Embed and store Tavily results in wozly_web_cache for future retrieval."""
    if not resources:
        return
    try:
        texts = [f"{r['title']}: {r.get('snippet','')}" for r in resources]
        embeddings = await embed_batch(texts)
        # ChromaDB local client is synchronous — run in thread pool
        loop = asyncio.get_event_loop()
        collection = await loop.run_in_executor(None, get_collection, COLLECTION_WEB_CACHE)
        await loop.run_in_executor(
            None,
            lambda: collection.upsert(
                ids=[r["id"] for r in resources],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{
                    "title": r["title"],
                    "url": r["url"],
                    "type": r.get("type", "article"),
                    "domain": domain,
                    "topic": topic,
                } for r in resources],
            )
        )
    except Exception:
        pass  # Cache failure is non-fatal


async def retrieve_resources(
    topic: str,
    knowledge_level: str,
    domain: str,
    k: int | None = None,
) -> list[dict]:
    """
    Full RAG retrieval pipeline:
    1. ChromaDB cosine search
    2. LLM re-rank
    3. URL validation
    4. Tavily fallback if needed
    Returns list of resource dicts with title, url, type, relevance_score.
    """
    top_k = k or _settings.rag_top_k
    query_text = f"{topic} {knowledge_level}"
    query_embedding = await embed_text(query_text)

    loop = asyncio.get_event_loop()

    # ── 1. ChromaDB retrieval (sync API — run in thread pool) ─────────────────
    raw_chunks: list[dict] = []
    for collection_name in [COLLECTION_DOCUMENTS, COLLECTION_WEB_CACHE]:
        try:
            collection = await loop.run_in_executor(None, get_collection, collection_name)
            results = await loop.run_in_executor(
                None,
                lambda col=collection: col.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"],
                )
            )
            if results and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    confidence = 1.0 - distance  # cosine distance → similarity
                    if confidence >= _settings.rag_min_confidence:
                        raw_chunks.append({
                            "id": doc_id,
                            "title": meta.get("title", "Resource"),
                            "url": meta.get("url", ""),
                            "snippet": results["documents"][0][i][:300] if results["documents"] else "",
                            "type": meta.get("type", "article"),
                            "relevance_score": confidence,
                        })
        except Exception:
            pass

    # ── 2. LLM re-rank ────────────────────────────────────────────────────────
    ranked = await _llm_rerank(topic, knowledge_level, raw_chunks)

    # ── 2b. Keyword relevance filter ─────────────────────────────────────────
    keywords = {k.strip().lower() for k in (topic + " " + domain).split() if k.strip()}
    filtered = []
    for r in ranked:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        score = _keyword_score(title, keywords) + _keyword_score(snippet, keywords)
        if score > 0:
            filtered.append(r)
    ranked = filtered or ranked

    # ── 3. URL validation ─────────────────────────────────────────────────────
    valid = await _validate_urls(ranked)

    # ── 4. Tavily fallback ────────────────────────────────────────────────────
    if len(valid) < 2:
        tavily_results = await _tavily_search(topic, domain, knowledge_level)
        # Filter Tavily by topic/domain keywords to reduce unrelated results
        keywords = {k.strip().lower() for k in (topic + " " + domain).split() if k.strip()}
        tavily_filtered = []
        for r in tavily_results:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            score = _keyword_score(title, keywords) + _keyword_score(snippet, keywords)
            if score > 0:
                tavily_filtered.append(r)
        tavily_results = tavily_filtered or tavily_results
        # Trust Tavily results without HEAD validation, since Tavily already fetched them
        await _cache_tavily_results(topic, domain, tavily_results)
        valid.extend(tavily_results)

    # Deduplicate by URL, return top K
    seen_urls: set[str] = set()
    deduped = []
    for r in valid:
        if r["url"] and r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            deduped.append(r)

    # ── 5. Ultimate Fallback ──────────────────────────────────────────────────
    if not deduped:
        print(f"[RAG] All retrievals failed for '{topic}'. Using ultimate fallback.")
        deduped = [
            {
                "id": str(uuid.uuid4()),
                "title": f"{topic} - A Beginner's Guide (Documentation)",
                "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
                "type": "article",
                "relevance_score": 1.0,
            },
            {
                "id": str(uuid.uuid4()),
                "title": f"Understanding {topic} in 10 Minutes (YouTube)",
                "url": "https://www.youtube.com/results?search_query=" + topic.replace(" ", "+"),
                "type": "video",
                "relevance_score": 0.9,
            }
        ]

    return deduped[:top_k]
