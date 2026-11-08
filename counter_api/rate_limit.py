"""Shared fixed windows, anchored at the first request, using Redis atomically."""

import hashlib
from functools import lru_cache

from django.conf import settings
from redis import Redis
from redis.exceptions import RedisError

from counter_api.exceptions import CounterAPIError, service_unavailable

# Do not use Django's cache: production intentionally ignores cache exceptions.
WINDOW_SCRIPT = """
local count = tonumber(redis.call('GET', KEYS[1]) or '0')
local ttl = redis.call('PTTL', KEYS[1])
if count >= tonumber(ARGV[1]) and ttl >= 0 then
    return {0, math.ceil(ttl / 1000)}
end
if ttl < 0 then
    redis.call('SET', KEYS[1], 1, 'PX', ARGV[2] * 1000)
else
    redis.call('INCR', KEYS[1])
end
return {1, math.ceil(redis.call('PTTL', KEYS[1]) / 1000)}
"""


@lru_cache(maxsize=4)
def get_redis(url):
    return Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)


class RateLimitExceeded(CounterAPIError):
    def __init__(self, retry_after):
        super().__init__(1020, "Client has made too many requests", 429)
        self.retry_after = max(1, retry_after)


def check_rate_limit(request, api_key):
    if api_key is not None:
        identity = f"key:{api_key.digest}"
        quota = settings.COUNTER_API_KEY_QUOTA
    else:
        identity = f"anonymous:{request.META.get('REMOTE_ADDR', '')}"
        quota = settings.COUNTER_API_ANONYMOUS_QUOTA

    digest = hashlib.sha256(identity.encode()).hexdigest()
    bucket = f"counter:rate:v1:{digest}"

    try:
        allowed, retry_after = get_redis(settings.REDIS_URL).eval(
            WINDOW_SCRIPT, 1, bucket, quota, settings.COUNTER_API_RATE_WINDOW_SECONDS
        )
    except RedisError:
        raise service_unavailable() from None

    if not allowed:
        raise RateLimitExceeded(retry_after)
