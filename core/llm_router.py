"""
llm_router.py

Centralized LLM routing with:
  - Proactive load balancing across providers based on budget scores
  - Circuit breaker per provider (auto-heals after 60s)
  - Per-user daily call quota
  - Response caching (keyed by SHA256(url + text[:200]))
  - Automatic batching with per-model batch size limits
"""
import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any

import redis.asyncio as aioredis
from groq import AsyncGroq

logger = logging.getLogger(__name__)


PROVIDERS = [
    {
        "name":       "groq_primary",
        "model":      "llama-3.3-70b-versatile",
        "client_type": "groq",
        "rpd_limit":  1_000,
        "tpm_limit":  12_000,
        "max_batch":  8,
        "max_output_tokens": 8192,
    },
    {
        "name":       "llama_8b",
        "model":      "llama-3.1-8b-instant",
        "client_type": "groq",
        "rpd_limit":  14_400,
        "tpm_limit":  6_000,
        "max_batch":  1,
        "max_output_tokens": 8192,
    },
    {
        "name":       "llama4_scout",
        "model":      "meta-llama/llama-4-scout-17b-16e-instruct",
        "client_type": "groq",
        "rpd_limit":  1_000,
        "tpm_limit":  30_000,
        "max_batch":  10,
        "max_output_tokens": 8192,
    },
    {
        "name":       "mistral",
        "model":      "mistral-large-latest",
        "client_type": "mistral",
        "rpd_limit":  9_999,
        "tpm_limit":  80_000,
        "max_batch":  5,
        "max_output_tokens": 32768,
    },
]


def _resolve_enabled_providers() -> list[dict]:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    mistral_key = os.getenv("MISTRAL_API_KEY", "").strip()

    enabled: list[dict] = []
    for p in PROVIDERS:
        if p["client_type"] == "groq" and not groq_key:
            continue
        if p["client_type"] == "mistral" and not mistral_key:
            continue
        enabled.append(p)

    return enabled

_RPD_KEY        = "llm:{name}:rpd_used"
_CIRCUIT_KEY    = "llm:{name}:circuit_open"
_USER_QUOTA_KEY = "llm:user:{user_id}:today:calls"
_CACHE_KEY      = "llm_cache:{digest}"

USER_DAILY_CALL_LIMIT = int(os.getenv("LLM_USER_DAILY_LIMIT", "30"))
CIRCUIT_OPEN_TTL      = 60
CACHE_TTL             = 3600
CIRCUIT_FAIL_THRESH   = 3


class LLMRouter:
    """
    Single entry point for all LLM calls in the application.
    Usage:
        router = LLMRouter(redis_client)
        result = await router.complete(system, user_messages, cache_key=url)
    """
    def __init__(self, redis: aioredis.Redis):
        self._redis = redis
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self._groq  = AsyncGroq(api_key=groq_key) if groq_key else None
        self._providers = _resolve_enabled_providers()
        self._fail_counts: dict[str, int] = {}


    async def complete(
        self,
        system: str,
        user_content: str,
        *,
        user_id: str | None = None,
        cache_key: str | None = None,
        response_format: dict | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Route a single-turn completion through the best available provider.
        Checks cache first.  Enforces per-user quota.
        """
        if cache_key:
            cached = await self._get_cache(cache_key, user_content)
            if cached:
                logger.info("[LLMRouter] Cache HIT for key=%s", cache_key[:40])
                return cached

        if user_id:
            await self._enforce_user_quota(user_id)

        result = await self._dispatch(
            system, user_content, response_format=response_format, max_tokens=max_tokens
        )

        if cache_key and result:
            await self._set_cache(cache_key, user_content, result)

        return result

    async def _dispatch(
        self, system: str, user_content: str,
        response_format: dict | None, max_tokens: int
    ) -> str:
        provider_order = await self._rank_providers()

        last_error: Exception | None = None
        for provider in provider_order:
            name = provider["name"]
            if await self._is_circuit_open(name):
                logger.warning("[LLMRouter] Circuit OPEN for %s — skipping", name)
                continue

            try:
                t0 = time.perf_counter()
                capped_tokens = min(max_tokens, provider.get("max_output_tokens", 8192))
                result = await self._call_provider(
                    provider, system, user_content,
                    response_format=response_format, max_tokens=capped_tokens
                )
                elapsed = time.perf_counter() - t0

                await self._increment_rpd(name)
                self._fail_counts[name] = 0
                logger.info(
                    "[LLMRouter] provider=%s model=%s latency=%.2fs",
                    name, provider["model"], elapsed
                )
                return result

            except Exception as exc:
                logger.warning("[LLMRouter] %s failed: %s", name, exc)
                last_error = exc
                await self._record_failure(name)

        raise RuntimeError(
            f"All LLM providers exhausted or rate-limited. Last error: {last_error}"
        )

    async def _rank_providers(self) -> list[dict]:
        """Sort providers by load score = rpd_used / rpd_limit (ascending)."""
        if not self._providers:
            raise RuntimeError(
                "No LLM provider configured. Set MISTRAL_API_KEY (required) and optionally GROQ_API_KEY."
            )

        scored = []
        for p in self._providers:
            used = int(await self._redis.get(_RPD_KEY.format(name=p["name"])) or 0)
            score = used / p["rpd_limit"]
            if used < p["rpd_limit"]:
                scored.append((score, p))
        scored.sort(key=lambda x: x[0])
        return [p for _, p in scored]

    async def _call_provider(
        self, provider: dict, system: str, user_content: str,
        response_format: dict | None, max_tokens: int
    ) -> str:
        if provider["client_type"] == "groq":
            return await self._call_groq(
                provider["model"], system, user_content,
                response_format=response_format, max_tokens=max_tokens
            )
        elif provider["client_type"] == "mistral":
            return await self._call_mistral(
                provider["model"], system, user_content,
                response_format=response_format, max_tokens=max_tokens
            )
        else:
            raise ValueError(f"Unknown client_type: {provider['client_type']}")

    async def _call_groq(
        self, model: str, system: str, user_content: str,
        response_format: dict | None, max_tokens: int
    ) -> str:
        if self._groq is None:
            raise RuntimeError("GROQ_API_KEY is not configured")

        kwargs: dict[str, Any] = {
            "model":      model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system",  "content": system},
                {"role": "user",    "content": user_content},
            ],
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = await asyncio.wait_for(
            self._groq.chat.completions.create(**kwargs),
            timeout=30.0
        )
        return resp.choices[0].message.content.strip()

    async def _call_mistral(
        self, model: str, system: str, user_content: str,
        response_format: dict | None, max_tokens: int
    ) -> str:
        from mistralai.client import Mistral
        client = Mistral(api_key=os.getenv("MISTRAL_API_KEY", ""))
        kwargs: dict[str, Any] = {
            "model":      model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_content},
            ],
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = await asyncio.wait_for(
            client.chat.complete_async(**kwargs),
            timeout=30.0
        )
        return resp.choices[0].message.content.strip()
    async def _is_circuit_open(self, name: str) -> bool:
        return bool(await self._redis.exists(_CIRCUIT_KEY.format(name=name)))
    async def _record_failure(self, name: str) -> None:
        self._fail_counts[name] = self._fail_counts.get(name, 0) + 1
        if self._fail_counts[name] >= CIRCUIT_FAIL_THRESH:
            await self._redis.set(
                _CIRCUIT_KEY.format(name=name), 1, ex=CIRCUIT_OPEN_TTL
            )
            logger.error("[LLMRouter] Circuit TRIPPED for %s (60s cooldown)", name)
            self._fail_counts[name] = 0

    async def _increment_rpd(self, name: str) -> None:
        key = _RPD_KEY.format(name=name)
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        await pipe.execute()

    async def _enforce_user_quota(self, user_id: str) -> None:
        key = _USER_QUOTA_KEY.format(user_id=user_id)
        count = int(await self._redis.get(key) or 0)
        if count >= USER_DAILY_CALL_LIMIT:
            raise RuntimeError(
                f"Daily AI usage limit reached for user {user_id}. "
                f"Try again tomorrow or reduce your pipeline scope."
            )
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        await pipe.execute()

    def _cache_digest(self, key: str, content: str) -> str:
        raw = f"{key}::{content[:200]}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _get_cache(self, key: str, content: str) -> str | None:
        digest = self._cache_digest(key, content)
        val = await self._redis.get(_CACHE_KEY.format(digest=digest))
        return val.decode() if val else None

    async def _set_cache(self, key: str, content: str, result: str) -> None:
        digest = self._cache_digest(key, content)
        await self._redis.set(
            _CACHE_KEY.format(digest=digest), result, ex=CACHE_TTL
        )
def get_provider_max_batch(provider_name: str = "groq_primary") -> int:
    for p in PROVIDERS:
        if p["name"] == provider_name:
            return p["max_batch"]
    return 5

async def get_router(redis_url: str | None = None) -> LLMRouter:
    """Factory: create a router connected to Redis."""
    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = await aioredis.from_url(url, decode_responses=True)
    return LLMRouter(r)