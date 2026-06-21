from django.db import models
from django.utils.translation import gettext_lazy as _

from log_manager.models import LogFile
from tracker import choices
from tracker.exceptions import LogFileDiscardedLineCreateError


class LogFileDiscardedLine(models.Model):
    created = models.DateTimeField(verbose_name=_("Creation date"), auto_now_add=True)
    log_file = models.ForeignKey(
        LogFile,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        db_index=True,
    )
    error_type = models.CharField(
        _("Error Type"),
        choices=choices.LOG_FILE_DISCARDED_LINE_REASON,
        max_length=3,
        null=True,
        blank=True,
    )
    data = models.JSONField(
        _("Data"),
        default=dict,
    )
    message = models.TextField(
        _("Message"),
        null=True,
        blank=True,
    )
    handled = models.BooleanField(_("Handled"), default=False)

    @classmethod
    def create(cls, log_file, error_type, data, message, save=False):
        try:
            obj = cls()
            obj.log_file = log_file
            obj.error_type = error_type
            obj.data = data
            obj.message = message
            if save:
                obj.save()
        except Exception as exc:
            raise LogFileDiscardedLineCreateError(
                f"Unable to create LogFileDiscardedLine ({data} - {error_type} - {message}). EXCEPTION {exc}"
            )
        return obj

    def __str__(self):
        return f"{self.data} - {self.message}"
