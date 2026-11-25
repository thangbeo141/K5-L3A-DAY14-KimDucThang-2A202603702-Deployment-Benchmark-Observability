"""
Rate limiting (tiêu chí 7) — sliding window 60s lưu trong Redis sorted set.
"""
import time
import uuid
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    """Giới hạn RATE_LIMIT_PER_MINUTE request / 60 giây cho mỗi API key."""
    if r is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    now = time.time()
    window_seconds = 60
    redis_key = f"ratelimit:{key}"

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
        pipe.zcard(redis_key)
        _, current_count = pipe.execute()

        if current_count >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(window_seconds)},
            )

        member = f"{now}:{uuid.uuid4().hex[:8]}"
        pipe = r.pipeline()
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, window_seconds)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
