import json
import logging
import traceback
import uuid

from datetime import datetime

from django.core.files.base import ContentFile
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import CommonControlField
from log_manager.models import LogFile
from tracker import choices

from .exceptions import *


class LogFileDiscardedLine(CommonControlField):
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
    handled = models.BooleanField(
        _("Handled"),
        default=False
    )

    @classmethod
    def create(cls, log_file, error_type, data, message):
        try:
            obj = cls()
            obj.log_file = log_file
            obj.error_type = error_type
            obj.data = data
            obj.message = message
            obj.save()
        except Exception as exc:
            raise LogFileDiscardedLineCreateError(
                f"Unable to create LogFileDiscardedLine ({data} - {error_type} - {message}). EXCEPTION {exc}"
            )
        return obj

    def __str__(self):
        return f"{self.data} - {self.message}"


class UnexpectedEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(verbose_name=_("Creation date"), auto_now_add=True)
    exception_type = models.TextField(_("Exception Type"), null=True, blank=True)
    exception_msg = models.TextField(_("Exception Msg"), null=True, blank=True)
    traceback = models.JSONField(null=True, blank=True)
    detail = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["exception_type"]),
        ]

    def __str__(self):
        return f"{self.exception_msg}"

    @property
    def data(self):
        return dict(
            created=self.created.isoformat(),
            exception_type=self.exception_type,
            exception_msg=self.exception_msg,
            traceback=json.dumps(self.traceback),
            detail=json.dumps(self.detail),
        )

    @classmethod
    def create(
        cls,
        exception=None,
        exc_traceback=None,
        detail=None,
    ):
        try:
            if exception:
                logging.exception(exception)

            obj = cls()
            obj.exception_msg = str(exception)
            obj.exception_type = str(type(exception))
            try:
                json.dumps(detail)
                obj.detail = detail
            except Exception as e:
                obj.detail = str(detail)

            if exc_traceback:
                obj.traceback = traceback.format_tb(exc_traceback)
            obj.save()
            return obj
        except Exception as exc:
            raise UnexpectedEventCreateError(
                f"Unable to create unexpected event ({exception} {exc_traceback}). EXCEPTION {exc}"
            )


class Event(CommonControlField):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.TextField(_("Message"), null=True, blank=True)
    message_type = models.CharField(
        _("Message type"),
        choices=choices.EVENT_MSG_TYPE,
        max_length=16,
        null=True,
        blank=True,
    )
    detail = models.JSONField(null=True, blank=True)
    unexpected_event = models.ForeignKey(
        'UnexpectedEvent', on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["message_type"]),
        ]

    @property
    def data(self):
        d = {}
        d["created"] = self.created.isoformat()
        d["user"] = self.user.username
        d.update(
            dict(
                message=self.message, message_type=self.message_type, detail=self.detail
            )
        )
        if self.unexpected_event:
            d.update(self.unexpected_event.data)
        return d

    @classmethod
    def create(
        cls,
        user=None,
        message_type=None,
        message=None,
        e=None,
        exc_traceback=None,
        detail=None,
    ):
        try:
            obj = cls()
            obj.creator = user
            obj.message = message
            obj.message_type = message_type
            obj.detail = detail
            obj.save()

            if e:
                logging.exception(f"{message}: {e}")
                obj.unexpected_event = UnexpectedEvent.create(
                    exception=e,
                    exc_traceback=exc_traceback,
                )
                obj.save()
        except Exception as exc:
            raise EventCreateError(
                f"Unable to create Event ({message} {e}). EXCEPTION: {exc}"
            )
        return obj


def tracker_file_directory_path(instance, filename):
    d = datetime.now(datetime.timezone.utc)
    return f"tracker/{d.year}/{d.month}/{d.day}/{filename}"


class EventReport(CommonControlField):
    file = models.FileField(
        upload_to=tracker_file_directory_path, null=True, blank=True
    )

    class Meta:
        abstract = True

    def save_file(self, events, ext=None):
        if not events:
            return
        try:
            ext = ".json"
            content = json.dumps(list([item.data for item in events]))
            name = datetime.now(datetime.timezone.utc).isoformat() + ext
            self.file.save(name, ContentFile(content))
            self.delete_events(events)
        except Exception as e:
            raise EventReportSaveFileError(
                f"Unable to save EventReport.file ({name}). Exception: {e}"
            )

    def delete_events(self, events):
        for item in events:
            try:
                item.unexpected_event.delete()
            except:
                pass
            try:
                item.delete()
            except:
                pass

    @classmethod
    def create(cls, user):
        try:
            obj = cls()
            obj.creator = user
            obj.save()
        except Exception as e:
            raise EventReportCreateError(
                f"Unable to create EventReport. Exception: {e}"
            )
