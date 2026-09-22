import os
import subprocess
import sys

from django.test import SimpleTestCase

from metrics.tasks.daily_metric_exports import task_build_and_export_daily_metric_job


class CeleryConfigurationTests(SimpleTestCase):
    def test_daily_metric_job_has_effective_time_limits(self):
        self.assertEqual(task_build_and_export_daily_metric_job.soft_time_limit, 79200)
        self.assertEqual(task_build_and_export_daily_metric_job.time_limit, 86400)

    def test_daily_metric_job_time_limits_from_environment(self):
        command = [
            sys.executable,
            "-c",
            "import django; django.setup(); "
            "from metrics.tasks.daily_metric_exports import "
            "task_build_and_export_daily_metric_job as task; "
            "print(task.soft_time_limit, task.time_limit)",
        ]
        environment = os.environ.copy()
        environment["CELERY_DAILY_JOB_SOFT_TIME_LIMIT_SECONDS"] = "3600"
        environment["CELERY_DAILY_JOB_TIME_LIMIT_SECONDS"] = "7200"

        configured = subprocess.run(
            command,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(configured.stdout.strip(), "3600 7200")

        environment["CELERY_DAILY_JOB_SOFT_TIME_LIMIT_SECONDS"] = "7200"
        invalid = subprocess.run(
            command,
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("soft time limit must be positive and less", invalid.stderr)

    def test_redis_visibility_timeout_default_and_override(self):
        command = [
            sys.executable,
            "-c",
            "from config import celery_app; "
            "print(celery_app.conf.broker_transport_options['visibility_timeout'])",
        ]
        environment = os.environ.copy()
        environment.pop("CELERY_REDIS_VISIBILITY_TIMEOUT_SECONDS", None)

        default = subprocess.run(
            command,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(default.stdout.strip(), "3600")

        environment["CELERY_REDIS_VISIBILITY_TIMEOUT_SECONDS"] = "93600"
        configured = subprocess.run(
            command,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(configured.stdout.strip(), "93600")
