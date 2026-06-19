from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import get_settings
from app.services.client_identity import resolve_client_identity

_redis_client: Redis | None = None
_in_memory_buckets: dict[str, deque[float]] = defaultdict(deque)


async def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _request_identity(request: Request) -> str:
    client_host = request.client.host if request.client and request.client.host else ""
    settings = get_settings()
    trusted_proxies = {ip for ip in settings.trusted_proxy_ip_list if ip}
    forwarded_for = request.headers.get("x-forwarded-for", "")
    return resolve_client_identity(
        client_host=client_host,
        forwarded_for=forwarded_for,
        trusted_proxy_ips=trusted_proxies,
    )


async def enforce_rate_limit(
    *,
    request: Request,
    bucket: str,
    limit: int,
    window_seconds: int,
) -> None:
    identifier = _request_identity(request)
    key = f"rate_limit:{bucket}:{identifier}"
    retry_after = window_seconds
    try:
        redis = await _get_redis_client()
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        if current > limit:
            retry_after = max(await redis.ttl(key), 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        return
    except HTTPException:
        raise
    except Exception:
        pass

    now = time.time()
    queue = _in_memory_buckets[key]
    while queue and now - queue[0] >= window_seconds:
        queue.popleft()
    if len(queue) >= limit:
        retry_after = max(1, int(window_seconds - (now - queue[0])))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )
    queue.append(now)


def is_origin_allowed(origin: str) -> bool:
    normalized = origin.rstrip("/")
    settings = get_settings()
    return normalized in {item.rstrip("/") for item in settings.cors_origin_list}
