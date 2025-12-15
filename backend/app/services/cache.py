import hashlib
import logging
from typing import Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> Optional[redis.Redis]:
    """Return a shared Redis client or None if not configured/available.

    We fail soft: if Redis is down or REDIS_URL is not set, caching is simply
    skipped and the normal LLM path runs.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    url = getattr(settings, "REDIS_URL", None)
    if not url:
        return None

    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        # Light ping to verify connection; fail soft on error.
        client.ping()
        _redis_client = client
        logger.info("Redis cache initialised at %s", url)
        return _redis_client
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to initialise Redis client; disabling cache")
        _redis_client = None
        return None


def _normalise_jd(jd_text: str) -> str:
    """Normalise JD text for stable hashing.

    Lowercase and collapse whitespace so trivial formatting differences don't
    break cache hits.
    """
    if not jd_text:
        return ""
    return " ".join(jd_text.lower().split())


def _jd_hash(jd_text: str) -> str:
    norm = _normalise_jd(jd_text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def get_cached_job_summary(job_description: str) -> Optional[str]:
    """Return cached JD summary for this description, if any."""
    client = _get_redis()
    if not client:
        return None
    key = f"jd_summary:{_jd_hash(job_description)}"
    try:
        return client.get(key)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Redis error getting job summary")
        return None


def set_cached_job_summary(job_description: str, summary: str, ttl_seconds: int = 7 * 24 * 3600) -> None:
    """Cache JD summary for this description with a TTL (default 7 days)."""
    client = _get_redis()
    if not client:
        return
    key = f"jd_summary:{_jd_hash(job_description)}"
    try:
        client.setex(key, ttl_seconds, summary)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Redis error setting job summary")


def get_cached_selected_resume_lines(job_description: str, resume_id: int) -> Optional[str]:
    """Return cached selected resume lines for (JD, resume_id), if any."""
    client = _get_redis()
    if not client:
        return None
    key = f"jd_resume:{_jd_hash(job_description)}:{resume_id}"
    try:
        return client.get(key)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Redis error getting selected resume lines")
        return None


def set_cached_selected_resume_lines(
    job_description: str,
    resume_id: int,
    selected_lines: str,
    ttl_seconds: int = 7 * 24 * 3600,
) -> None:
    """Cache selected resume lines for (JD, resume_id)."""
    client = _get_redis()
    if not client:
        return
    key = f"jd_resume:{_jd_hash(job_description)}:{resume_id}"
    try:
        client.setex(key, ttl_seconds, selected_lines)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Redis error setting selected resume lines")




