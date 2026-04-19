"""Unified LLM client — supports Groq, GitHub Models, and SambaNova.

Primary:  Groq (llama-3.3-70b-versatile) — 14,400 req/day FREE
Fallback: GitHub Models (gpt-4o)
Legacy:   SambaNova (role-dedicated keys)
"""
from __future__ import annotations
import asyncio
from typing import AsyncIterator, Callable, Awaitable
from openai import (
    AsyncOpenAI,
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    RateLimitError,
)
from app.core.config import get_settings

_settings = get_settings()

# ── Cached clients ────────────────────────────────────────────────────────────
_role_clients: dict[str, AsyncOpenAI] = {}
_groq_client:   AsyncOpenAI | None = None
_github_client: AsyncOpenAI | None = None


def _get_groq_client() -> AsyncOpenAI:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncOpenAI(
            api_key=_settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return _groq_client


def _get_github_client() -> AsyncOpenAI:
    global _github_client
    if _github_client is None:
        _github_client = AsyncOpenAI(
            api_key=_settings.github_token,
            base_url=_settings.github_models_base_url,
        )
    return _github_client


def _get_groq_model(role: str) -> str:
    """Best Groq model — llama-3.3-70b for quality, 70b fits free tier fine."""
    return "llama-3.3-70b-versatile"


def _get_dedicated_api_key(role: str) -> str:
    key_map = {
        "roadmap":    _settings.sambanova_roadmap_api_key,
        "content":    _settings.sambanova_content_api_key,
        "profile":    _settings.sambanova_content_api_key,
        "tutor":      _settings.sambanova_tutor_api_key,
        "assessment": _settings.sambanova_assessment_api_key,
    }
    key = key_map.get(role, _settings.sambanova_roadmap_api_key)
    if not key:
        for k in [_settings.sambanova_roadmap_api_key, _settings.sambanova_content_api_key,
                  _settings.sambanova_tutor_api_key, _settings.sambanova_assessment_api_key]:
            if k: return k
    return key


def _build_sambanova_client(role: str) -> AsyncOpenAI:
    api_key = _get_dedicated_api_key(role)
    if not api_key:
        raise ValueError(f"No SambaNova API key for role '{role}'.")
    return AsyncOpenAI(api_key=api_key, base_url="https://api.sambanova.ai/v1")


def get_sambanova_client(role: str) -> AsyncOpenAI:
    if role not in _role_clients:
        _role_clients[role] = _build_sambanova_client(role)
    return _role_clients[role]


def _get_retry_after_seconds(error: Exception) -> float | None:
    headers = getattr(getattr(error, "response", None), "headers", None)
    if not headers:
        return None
    val = headers.get("retry-after") or headers.get("Retry-After")
    if val:
        try:
            return float(val)
        except ValueError:
            return None
    return None


async def _call_with_retries(
    call_factory: Callable[[], Awaitable[object]],
    role: str = "profile",
    max_attempts: int = 4,
) -> object:
    """
    Execute call_factory with smart retry logic.

    On 429 (RateLimitError):
      - The SAME dedicated key is used (no rotation — each role has its own key)
      - Waits for the retry-after header time, or 15s if not provided
      - Attempts up to max_attempts times

    On persistent failure:
      - Falls back to GitHub Models if configured
    """
    attempt = 0
    base_delay = 2.0

    while attempt < max_attempts:
        try:
            result = await call_factory()
            return result
        except RateLimitError as exc:
            attempt += 1
            # Honor the retry-after header if present
            retry_after = _get_retry_after_seconds(exc)
            wait = retry_after if retry_after else (15.0 + attempt * 5.0)
            print(f"[LLM] Role '{role}' — 429 Rate Limited (attempt {attempt}/{max_attempts}). Waiting {wait:.0f}s...")
            await asyncio.sleep(wait)
        except (APIStatusError, APIConnectionError, APITimeoutError) as exc:
            attempt += 1
            status_code = getattr(exc, "status_code", None)
            # Don't retry on client errors (4xx except 429)
            if status_code and 400 <= status_code < 500 and status_code != 429:
                raise
            if attempt >= max_attempts:
                raise
            wait = base_delay * (2 ** attempt)
            print(f"[LLM] Role '{role}' — API error {status_code}, retrying in {wait:.1f}s...")
            await asyncio.sleep(wait)

    raise RuntimeError(f"[LLM] Role '{role}' exhausted all {max_attempts} attempts.")


# ── GitHub Models fallback client ─────────────────────────────────────────────
_github_client: AsyncOpenAI | None = None

def _get_github_client() -> AsyncOpenAI:
    global _github_client
    if _github_client is None:
        _github_client = AsyncOpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=_settings.github_token or "no-token",
        )
    return _github_client


# ── Core completion helpers ────────────────────────────────────────────────────

async def chat_complete(
    system: str,
    user: str,
    role: str = "profile",
    temperature: float = 0.3,
    max_tokens: int = 2000,
    json_mode: bool = False,
    provider_override: str | None = None,
) -> str:
    """
    Single-turn chat completion.

    Priority:
    1. Groq  (llama-3.3-70b) — 14,400 req/day, fast
    2. GitHub Models (gpt-4o) — fallback if Groq fails
    3. SambaNova — legacy, only if explicitly set as provider
    """
    provider = provider_override or _settings.llm_provider

    kwargs: dict = dict(
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    # Enable json_object mode for all providers that support it
    # Note: llama-3.3-70b-versatile on Groq DOES support response_format json_object
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    # ── Groq (primary) ────────────────────────────────────────────────────────
    if provider == "groq":
        try:
            res = await _get_groq_client().chat.completions.create(
                model=_get_groq_model(role),
                **kwargs,
            )
            return res.choices[0].message.content
        except RateLimitError:
            print(f"[LLM] Groq 429 for role '{role}' — waiting 3s then trying GitHub Models...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[LLM] Groq error for role '{role}': {e} — falling back to GitHub...")

        # Fallback to GitHub
        if _settings.github_token:
            try:
                res = await _get_github_client().chat.completions.create(
                    model="gpt-4o",
                    **{**kwargs, "response_format": {"type": "json_object"} if json_mode else {}},
                )
                return res.choices[0].message.content
            except Exception as ge:
                print(f"[LLM] GitHub fallback also failed: {ge}")
        raise RuntimeError(f"All providers failed for role '{role}'")

    # ── GitHub Models ─────────────────────────────────────────────────────────
    if provider == "github":
        try:
            res = await _get_github_client().chat.completions.create(
                model="gpt-4o",
                **{**kwargs, "response_format": {"type": "json_object"} if json_mode else {}},
            )
            return res.choices[0].message.content
        except RateLimitError:
            print(f"[LLM] GitHub 429 for role '{role}' — trying Groq fallback...")
            if _settings.groq_api_key:
                res = await _get_groq_client().chat.completions.create(
                    model=_get_groq_model(role), **kwargs
                )
                return res.choices[0].message.content
            raise

    # ── SambaNova (legacy) ────────────────────────────────────────────────────
    if provider == "sambanova":
        try:
            client = get_sambanova_client(role)
            model_map = {
                "roadmap": _settings.sambanova_roadmap_model,
                "content": _settings.sambanova_content_model,
                "profile": _settings.sambanova_content_model,
                "tutor":   _settings.sambanova_tutor_model,
                "assessment": _settings.sambanova_assessment_model,
            }
            m = model_map.get(role, _settings.sambanova_roadmap_model)
            res = await client.chat.completions.create(model=m, **kwargs)
            return res.choices[0].message.content
        except RateLimitError:
            print(f"[LLM] SambaNova 429 for role '{role}' — falling back to Groq...")
            if _settings.groq_api_key:
                res = await _get_groq_client().chat.completions.create(
                    model=_get_groq_model(role), **kwargs
                )
                return res.choices[0].message.content
            raise

    raise ValueError(f"Unsupported provider: {provider}")


async def chat_complete_messages(
    messages: list[dict],
    role: str = "tutor",
    temperature: float = 0.5,
    max_tokens: int = 600,
    json_mode: bool = False,
    provider_override: str | None = None,
) -> str:
    """Multi-turn chat completion (with conversation history)."""
    provider = provider_override or _settings.llm_provider

    kwargs: dict = dict(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # ── Groq (primary) ────────────────────────────────────────────────────────
    if provider == "groq":
        try:
            res = await _get_groq_client().chat.completions.create(
                model=_get_groq_model(role), **kwargs
            )
            return res.choices[0].message.content
        except RateLimitError:
            print(f"[LLM] Groq 429 for role '{role}' — falling back to GitHub Models...")
        except Exception as e:
            print(f"[LLM] Groq error for role '{role}': {e} — falling back to GitHub...")
        if _settings.github_token:
            try:
                res = await _get_github_client().chat.completions.create(
                    model="gpt-4o", **kwargs
                )
                return res.choices[0].message.content
            except Exception as ge:
                print(f"[LLM] GitHub fallback also failed: {ge}")
        raise RuntimeError(f"All providers failed for role '{role}'")

    # ── GitHub (direct) ───────────────────────────────────────────────────────
    if provider == "github":
        res = await _get_github_client().chat.completions.create(
            model="gpt-4o", **kwargs
        )
        return res.choices[0].message.content

    # ── SambaNova (legacy) ────────────────────────────────────────────────────
    if provider == "sambanova":
        model_map = {
            "roadmap": _settings.sambanova_roadmap_model,
            "content": _settings.sambanova_content_model,
            "profile": _settings.sambanova_content_model,
            "tutor":   _settings.sambanova_tutor_model,
            "assessment": _settings.sambanova_assessment_model,
        }
        m = model_map.get(role, _settings.sambanova_roadmap_model)
        try:
            client = get_sambanova_client(role)
            res = await _call_with_retries(
                lambda: client.chat.completions.create(model=m, **kwargs),
                role=role,
            )
            return res.choices[0].message.content
        except Exception as primary_err:
            print(f"[LLM] SambaNova failed: {primary_err} — trying Groq...")
            if _settings.groq_api_key:
                res = await _get_groq_client().chat.completions.create(
                    model=_get_groq_model(role), **kwargs
                )
                return res.choices[0].message.content
            raise

    raise ValueError(f"Unsupported provider: {provider}")


async def stream_complete_messages(
    messages: list[dict],
    role: str = "tutor",
    temperature: float = 0.5,
    max_tokens: int = 600,
) -> AsyncIterator[str]:
    """Streaming chat completion — yields text chunks."""
    provider = _settings.llm_provider

    # ── Groq streaming ────────────────────────────────────────────────────────
    if provider == "groq":
        try:
            stream = await _get_groq_client().chat.completions.create(
                model=_get_groq_model(role),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            return
        except Exception as e:
            print(f"[LLM] Groq stream failed: {e}")
            # Fall through to GitHub

    # ── GitHub streaming ──────────────────────────────────────────────────────
    if provider in ("github", "groq") and _settings.github_token:
        stream = await _get_github_client().chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
        return

    # ── SambaNova streaming ───────────────────────────────────────────────────
    if provider == "sambanova":
        model_map = {
            "tutor":      _settings.sambanova_tutor_model,
            "roadmap":    _settings.sambanova_roadmap_model,
            "content":    _settings.sambanova_content_model,
            "assessment": _settings.sambanova_assessment_model,
        }
        m = model_map.get(role, _settings.sambanova_tutor_model)
        client = get_sambanova_client(role)
        stream = await client.chat.completions.create(
            model=m,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
        return

    raise ValueError(f"Unsupported provider for streaming: {provider}")


# ── Backward-compatibility aliases ────────────────────────────────────────────
stream_complete = stream_complete_messages


def get_llm_client(role: str = "", provider_override: str | None = None) -> AsyncOpenAI:
    """
    Returns an AsyncOpenAI-compatible client for the given role.
    Used by embedder.py for creating embeddings.
    For SambaNova, returns the dedicated role client.
    For GitHub, returns the shared GitHub client.
    """
    provider = provider_override or _settings.llm_provider
    if provider == "sambanova":
        return get_sambanova_client(role or "roadmap")
    return _get_github_client()

