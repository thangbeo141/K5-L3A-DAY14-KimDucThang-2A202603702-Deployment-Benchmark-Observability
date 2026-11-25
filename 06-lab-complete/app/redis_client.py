"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis
from app.config import settings

try:
    r = redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
except Exception:
    r = None


def redis_healthy() -> bool:
    """Kiểm tra kết nối Redis cho GET /ready."""
    if r is None:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False
