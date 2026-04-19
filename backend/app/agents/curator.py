"""Content Curator Agent — RAG-powered resource retrieval.

Thin orchestration wrapper over the RAG retriever.
Called as a sub-agent by the Roadmap and Tutor agents.
"""
from app.rag.retriever import retrieve_resources


async def curate_resources(
    topics: list[str],
    knowledge_level: str,
    domain: str,
    max_per_topic: int = 3,
) -> dict[str, list[dict]]:
    """
    For each topic, retrieve the best learning resources.
    Returns dict mapping topic → list of resource dicts.
    """
    results: dict[str, list[dict]] = {}
    for topic in topics:
        resources = await retrieve_resources(topic, knowledge_level, domain)
        results[topic] = [
            {
                "title": r.get("title", topic),
                "url": r.get("url", ""),
                "type": r.get("type", "article"),
                "relevance_score": r.get("relevance_score", 0.5),
            }
            for r in resources[:max_per_topic]
        ]
    return results


async def curate_single_topic(
    topic: str,
    knowledge_level: str,
    domain: str,
) -> list[dict]:
    """Retrieve resources for a single topic (used by Tutor Agent)."""
    resources = await retrieve_resources(topic, knowledge_level, domain)
    return [
        {
            "title": r.get("title", topic),
            "url": r.get("url", ""),
            "type": r.get("type", "article"),
            "relevance_score": r.get("relevance_score", 0.5),
        }
        for r in resources[:3]
    ]
