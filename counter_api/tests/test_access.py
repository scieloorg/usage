import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from redis import Redis

from counter_api.models import APIKey
from counter_api.rate_limit import WINDOW_SCRIPT

DATA_PATHS = (
    "/r51/members",
    "/r51/platforms",
    "/r51/reports",
    "/r51/reports/tr",
    "/r51/extensions/capabilities",
    "/r51/extensions/ranking",
    "/r51/extensions/distribution",
)


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["public", "key_required"])
def test_invalid_keys_rejected_on_every_data_route(client, settings, mode):
    settings.COUNTER_API_ACCESS_MODE = mode
    revoked, revoked_value = APIKey.issue("revoked")
    revoked.active = False
    revoked.save()
    _, expired = APIKey.issue("expired", timezone.now() - timedelta(seconds=1))
    for path in DATA_PATHS:
        for value in ("", "invalid", revoked_value, expired):
            response = client.get(path, {"api_key": value})
            assert response.status_code == 401
            assert response.json() == {"Code": 2020, "Message": "APIKey Invalid"}
        response = client.get(path, {"api_key": ["invalid", "other"]})
        assert response.status_code == 401
    assert not APIKey.objects.exclude(last_used_at=None).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["public", "key_required"])
def test_mode_gate_and_admin_remain_separate(client, settings, mode):
    settings.COUNTER_API_ACCESS_MODE = mode
    key, value = APIKey.issue("client")
    for path in DATA_PATHS:
        response = client.get(path)
        assert (response.status_code == 401) == (mode == "key_required")
    assert client.get("/r51/platforms", {"api_key": value}).status_code == 200
    key.refresh_from_db()
    assert key.last_used_at is not None
    for name in ("admin:index", "wagtailadmin_home"):
        for params in ({}, {"api_key": value}):
            response = client.get(reverse(name), params)
            assert response.status_code == 302
            assert "/login/" in response.url


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["public", "key_required"])
def test_status_is_always_public_unmetered_and_ignores_keys(
    client, settings, mode
):
    settings.COUNTER_API_ACCESS_MODE = mode
    with patch("counter_api.access.APIKey.authenticate") as authenticate:
        for params in ({}, {"api_key": ""}, {"api_key": "invalid"}):
            assert client.get("/r51/status", params).status_code == 200
        authenticate.assert_not_called()
    assert client.get("/r51/").status_code == 200
    assert client.get("/r51/schema/").status_code == 200
    assert client.post("/r51/platforms").status_code == 405


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
