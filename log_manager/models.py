import logging

from django.db import IntegrityError, models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtailautocomplete.edit_handlers import AutocompletePanel

from collection.models import Collection
from core.utils.date_utils import get_date_obj

from log_manager import choices, file_errors


class LogFile(models.Model):
    created = models.DateTimeField(verbose_name=_("Creation date"), auto_now_add=True)
    updated = models.DateTimeField(verbose_name=_("Last update date"), auto_now=True)
    date = models.DateField(
        verbose_name=_("Date"), null=True, blank=True, db_index=True
    )
    hash = models.CharField(
        _("Hash MD5"), max_length=32, null=True, blank=True, unique=True
    )

    path = models.CharField(_("Name"), max_length=255, null=False, blank=False)

    stat_result = models.JSONField(_("OS Stat Result"), null=False, blank=False)

    status = models.CharField(
        _("Status"),
        choices=choices.LOG_FILE_STATUS,
        max_length=3,
        blank=False,
        null=False,
    )

    validation = models.JSONField(
        _("Validation"),
        null=True,
        blank=True,
        default=dict,
    )

    summary = models.JSONField(
        _("Summary"),
        null=True,
        blank=True,
        default=dict,
    )

    collection = models.ForeignKey(
        Collection,
        verbose_name=_("Collection"),
        on_delete=models.DO_NOTHING,
        null=False,
        blank=False,
    )

    last_processed_line = models.IntegerField(
        _("Last Processed Line"),
        blank=True,
        default=0,
    )

    parse_heartbeat_at = models.DateTimeField(
        _("Parse Heartbeat At"),
        null=True,
        blank=True,
    )

    panels = [
        FieldPanel("hash"),
        FieldPanel("date"),
        FieldPanel("path"),
        FieldPanel("stat_result"),
        FieldPanel("status"),
        FieldPanel("validation"),
        FieldPanel("summary"),
        FieldPanel("last_processed_line"),
        FieldPanel("parse_heartbeat_at"),
        AutocompletePanel("collection"),
    ]

    class Meta:
        verbose_name = _("Log File")
        verbose_name_plural = _("Log Files")

    @classmethod
    def create_or_update(cls, collection, path, stat_result, hash, status=None):
        try:
            obj, created = cls.objects.get_or_create(
                hash=hash,
                defaults={
                    "collection": collection,
                    "path": path,
                    "stat_result": stat_result,
                    "status": status or choices.LOG_FILE_STATUS_CREATED,
                },
            )
        except IntegrityError:
            obj = cls.objects.get(hash=hash)
            created = False

        if created:
            logging.info(f"File {path} added to the database.")
        else:
            obj.updated = timezone.now()
            obj.save(update_fields=["updated"])
            logging.info(f"File {path} already exists in the database.")

        return obj

    @classmethod
    def for_collection_date(cls, collection, access_date, status_filters=None):
        queryset = (
            cls.objects.filter(
                collection=collection,
                date=access_date,
            )
            .select_related("collection")
            .order_by("path", "hash")
        )
        if status_filters:
            queryset = queryset.filter(status__in=status_filters)

        queryset = _exclude_file_read_errors(queryset)

        return list(queryset)

    @classmethod
    def for_collection_date_hashes(cls, collection, access_date, log_hashes):
        return list(
            cls.objects.filter(
                collection=collection,
                date=access_date,
                hash__in=log_hashes,
            )
            .select_related("collection")
            .order_by("path", "hash")
        )

    @classmethod
    def distinct_access_dates_for_parsing(
        cls,
        collection,
        from_date,
        until_date,
        status_filters,
        skip_hashes=None,
    ):
        date_queryset = cls.objects.filter(
            status__in=status_filters,
            collection=collection,
            date__gte=from_date,
            date__lte=until_date,
        ).exclude(hash__in=skip_hashes or [])
        date_queryset = (
            _exclude_file_read_errors(date_queryset)
            .values_list("date", flat=True)
            .distinct()
            .order_by("date")
        )

        access_dates = set()
        for value in list(date_queryset):
            access_date = value if hasattr(value, "isoformat") else get_date_obj(value)
            if access_date and from_date <= access_date <= until_date:
                access_dates.add(access_date)
        return sorted(access_dates)

    def __str__(self):
        return f"{self.path}"


def _exclude_file_read_errors(queryset):
    read_error_ids = LogFile.objects.filter(
        status=choices.LOG_FILE_STATUS_ERROR,
        validation__file_error__code=file_errors.FILE_READ_ERROR_CODE,
    ).values_list("pk", flat=True)
    return queryset.exclude(pk__in=read_error_ids)
