"""Small in-memory limiter for a single API process."""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_buckets: dict[str, deque] = defaultdict(deque)


def client_address(request: Request) -> str:
    forwarded = (request.headers.get("x-real-ip") or "").strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    bucket = _buckets[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Try again shortly.")
    bucket.append(now)


def limit_auth_requests(request: Request) -> None:
    enforce_rate_limit(f"auth:{client_address(request)}", limit=30, window_seconds=60)


def limit_ai_requests(user_id: str) -> None:
    enforce_rate_limit(f"ai:{user_id}", limit=40, window_seconds=600)
