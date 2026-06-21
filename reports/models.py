from django.db import models
from django.utils.translation import gettext_lazy as _

from collection.models import Collection


class AbstractLogReport(models.Model):
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        verbose_name=_("Collection"),
    )
    total_files = models.IntegerField(default=0)
    created_files = models.IntegerField(default=0)
    validated_files = models.IntegerField(default=0)
    invalidated_files = models.IntegerField(default=0)
    errored_files = models.IntegerField(default=0)
    lines_parsed = models.IntegerField(default=0)
    valid_lines = models.IntegerField(default=0)
    discarded_lines = models.IntegerField(default=0)
    ip_local_count = models.IntegerField(default=0)
    ip_remote_count = models.IntegerField(default=0)
    ip_unknown_count = models.IntegerField(default=0)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def pct_validated(self):
        if not self.total_files:
            return 0
        return round(self.validated_files / self.total_files * 100, 1)

    pct_validated.fget.short_description = _("% Valid Files")

    @property
    def pct_valid_lines(self):
        if not self.lines_parsed:
            return 0
        return round(self.valid_lines / self.lines_parsed * 100, 1)

    pct_valid_lines.fget.short_description = _("% Valid Lines")

    @property
    def pct_remote_ip(self):
        total = self.ip_remote_count + self.ip_local_count
        if not total:
            return 0
        return round(self.ip_remote_count / total * 100, 1)

    pct_remote_ip.fget.short_description = _("% Remote IP")

    def __str__(self):
        return f"{self.collection.acron3} {self.period_label}"

    @property
    def period_label(self):
        raise NotImplementedError


class WeeklyLogReport(AbstractLogReport):
    year = models.IntegerField(verbose_name=_("Year"))
    week = models.IntegerField(verbose_name=_("ISO Week"))

    class Meta:
        unique_together = [("collection", "year", "week")]
        ordering = ["collection__acron3", "year", "week"]
        verbose_name = _("Weekly Log Report")
        verbose_name_plural = _("Weekly Log Reports")

    @property
    def period_label(self):
        return f"{self.year}-W{self.week:02d}"


class MonthlyLogReport(AbstractLogReport):
    year = models.IntegerField(verbose_name=_("Year"))
    month = models.IntegerField(verbose_name=_("Month"))

    class Meta:
        unique_together = [("collection", "year", "month")]
        ordering = ["collection__acron3", "year", "month"]
        verbose_name = _("Monthly Log Report")
        verbose_name_plural = _("Monthly Log Reports")

    @property
    def period_label(self):
        return f"{self.year}-{self.month:02d}"


class YearlyLogReport(AbstractLogReport):
    year = models.IntegerField(verbose_name=_("Year"))

    class Meta:
        unique_together = [("collection", "year")]
        ordering = ["collection__acron3", "year"]
        verbose_name = _("Yearly Log Report")
        verbose_name_plural = _("Yearly Log Reports")

    @property
    def period_label(self):
        return str(self.year)
