"""Valkey/Redis URL helpers shared by health checks, SSE and task backends."""


def normalize_redis_url(url: str) -> str:
    """Rewrite valkey:// to redis:// (and valkeys:// to rediss://).

    redis-py rejects any scheme other than redis://, rediss:// and unix://.
    Valkey is wire-compatible with Redis, so the rewrite is safe and keeps the
    shipped ``valkey://`` defaults working.
    """
    if url.startswith("valkeys://"):
        return "rediss://" + url[len("valkeys://") :]
    if url.startswith("valkey://"):
        return "redis://" + url[len("valkey://") :]
    return url
