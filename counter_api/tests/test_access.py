import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from redis import Redis

from counter_api.rate_limit import WINDOW_SCRIPT


def test_invalid_mode_fails_startup():
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings.base"],
        env={**os.environ, "COUNTER_API_ACCESS_MODE": "invalid"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert (
        "ValueError: COUNTER_API_ACCESS_MODE must be public or key_required"
        in result.stderr
    )


@pytest.mark.skipif(
    not os.environ.get("COUNTER_TEST_REDIS_URL"), reason="requires disposable Redis"
)
def test_real_redis_lua_is_atomic_and_window_expires():
    # Only a random, owned bucket is touched; never flush Redis.
    url = os.environ["COUNTER_TEST_REDIS_URL"]
    clients = [Redis.from_url(url) for _ in range(4)]
    bucket = f"counter:test:{uuid4().hex}"

    try:

        def attempt(index):
            return clients[index % 4].eval(WINDOW_SCRIPT, 1, bucket, 7, 2)

        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(attempt, range(50)))

        assert sum(result[0] for result in results) == 7
        assert all(1 <= result[1] <= 2 for result in results)
        assert clients[0].get(bucket) == b"7"
        assert 0 < clients[0].pttl(bucket) <= 2000

        time.sleep(2.05)
        assert attempt(0) == [1, 2]

    finally:
        clients[0].delete(bucket)
        for redis in clients:
            redis.close()
