import os
import subprocess
import sys


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
