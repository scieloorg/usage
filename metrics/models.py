from django.db import models
from django.utils.translation import gettext_lazy as _

from collection.models import Collection
from core.models import CommonControlField


class DailyMetricJob(CommonControlField):
    STATUS_PENDING = "PEN"
    STATUS_EXPORTING = "EXP"
    STATUS_EXPORTED = "SUC"
    STATUS_ERROR = "ERR"
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_EXPORTING, _("Exporting")),
        (STATUS_EXPORTED, _("Exported")),
        (STATUS_ERROR, _("Error")),
    )

    collection = models.ForeignKey(
        Collection,
        verbose_name=_("Collection"),
        on_delete=models.CASCADE,
        db_index=True,
    )

    access_date = models.DateField(
        verbose_name=_("Access Date"),
        db_index=True,
    )

    status = models.CharField(
        verbose_name=_("Status"),
        max_length=3,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    input_log_hashes = models.JSONField(
        verbose_name=_("Input Log Hashes"),
        default=list,
    )

    storage_path = models.CharField(
        verbose_name=_("Storage Path"),
        max_length=500,
        blank=True,
        default="",
    )

    payload_hash = models.CharField(
        verbose_name=_("Payload Hash"),
        max_length=64,
        blank=True,
        default="",
    )

    summary = models.JSONField(
        verbose_name=_("Summary"),
        default=dict,
        blank=True,
    )

    attempts = models.PositiveIntegerField(
        verbose_name=_("Attempts"),
        default=0,
    )

    error_message = models.TextField(
        verbose_name=_("Error Message"),
        blank=True,
        default="",
    )

    export_started_at = models.DateTimeField(
        verbose_name=_("Export Started At"),
        null=True,
        blank=True,
    )

    exported_at = models.DateTimeField(
        verbose_name=_("Exported At"),
        null=True,
        blank=True,
    )

    @property
    def input_log_count(self):
        return len(self.input_log_hashes or [])

    @property
    def job_id(self):
        if not self.payload_hash:
            return ""
        return f"{self.collection.acron3}|{self.access_date.isoformat()}|{self.payload_hash}"

    class Meta:
        verbose_name = _("Daily Metric Job")
        verbose_name_plural = _("Daily Metric Jobs")
        unique_together = (("collection", "access_date"),)
        indexes = [
            models.Index(
                fields=["collection", "access_date"], name="metrics_daily_coll_date_idx"
            ),
            models.Index(
                fields=["status", "export_started_at"],
                name="metrics_daily_status_exp_idx",
            ),
        ]

    def __str__(self):
        return f"{self.collection.acron3}-{self.access_date}"
