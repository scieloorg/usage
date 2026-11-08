from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def counter_redis():
    """Isolate Redis; integration tests opt in with COUNTER_TEST_REDIS_URL."""
    with patch("counter_api.rate_limit.get_redis") as get_redis:
        get_redis.return_value.eval.return_value = [1, 60]
        yield get_redis.return_value
