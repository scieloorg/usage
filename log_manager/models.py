from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtailautocomplete.edit_handlers import AutocompletePanel

from collection.models import Collection
from core.forms import CoreAdminModelForm
from core.models import CommonControlField

from . import choices


class LogFileDate(CommonControlField):
    date = models.DateField(
        verbose_name=_("Date"),
        null=False,
        blank=False,
    )

    log_file = models.ForeignKey(
        'LogFile',
        verbose_name=_('Log File'),
        blank=True,
        on_delete=models.DO_NOTHING,
    )

    base_form_class = CoreAdminModelForm

    panel = [
        FieldPanel('date'),
        AutocompletePanel('log_file')
    ]

    class Meta:
        ordering = ['-date']
        verbose_name = _("Log File Date")
        verbose_name_plural = _("Log File Dates")
        unique_together = (
            'date',
            'log_file',
        )

    @classmethod
    def create_or_update(cls, user, log_file, date):
        obj, created = cls.objects.get_or_create(
            log_file=log_file, 
            date=date,
        )

        if not created:
            obj.updated_by = user
            obj.updated = timezone.now()
        else:
            obj.creator = user
            obj.created = timezone.now()

        return obj
    
    @classmethod
    def filter_by_collection_and_date(cls, collection, date):
        return cls.objects.filter(
            ~Q(log_file__status__in=[
                choices.LOG_FILE_STATUS_CREATED, 
                choices.LOG_FILE_STATUS_INVALIDATED
            ]),
            log_file__collection__acron3=collection,
            date=date,
        )
        
    @classmethod
    def get_number_of_found_files_for_date(cls, collection, date):
        return cls.objects.filter(
            ~Q(log_file__status__in=[
                choices.LOG_FILE_STATUS_CREATED, 
                choices.LOG_FILE_STATUS_INVALIDATED
            ]),
            log_file__collection__acron3=collection,
            date=date,
        ).count()

    def __str__(self):
        return f'{self.log_file.path}-{self.date}'


class CollectionLogFileDateCount(CommonControlField):
    collection = models.ForeignKey(
        Collection, 
        verbose_name=_('Collection'), 
        on_delete=models.DO_NOTHING, 
        null=False, 
        blank=False,
    )

    date = models.DateField(
        _('Date'),
        null=False,
        blank=False,
    )
    
    year = models.IntegerField(
        _('Year'),
        null=False,
        blank=False,
    )
    
    month = models.IntegerField(
        _('Month'),
        null=False,
        blank=False,
    )

    found_log_files = models.IntegerField(
        verbose_name=_('Number of Found Valid Log Files'), 
        default=0,
    )

    expected_log_files = models.IntegerField(
        verbose_name=_('Number of Expected Valid Log Files'),
        blank=True,
        null=True,
    )
    
    status = models.CharField(
        verbose_name=_('Status'),
        choices=choices.COLLECTION_LOG_FILE_DATE_COUNT,
        max_length=3,
    )
    
    @classmethod
    def create_or_update(cls, user, collection, date, expected_log_files, found_log_files):
        obj, created = cls.objects.get_or_create(
            collection=collection, 
            date=date,
            month=date.month,
            year=date.year,
        )

        if not created:
            obj.updated_by = user
            obj.updated = timezone.now()
        else:
            obj.creator = user
            obj.created = timezone.now()

        obj.expected_log_files = expected_log_files            
        obj.found_log_files = found_log_files
        
        if found_log_files < expected_log_files:
            obj.status = choices.COLLECTION_LOG_FILE_DATE_COUNT_MISSING_FILES
        elif found_log_files > expected_log_files:
            obj.status = choices.COLLECTION_LOG_FILE_DATE_COUNT_EXTRA_FILES
        else:
            obj.status = choices.COLLECTION_LOG_FILE_DATE_COUNT_OK 
        
        obj.save()
        return obj
    
    class Meta:
        ordering = ['-date']
        verbose_name = _("Collection Log File Date Count")
        unique_together = (
            'collection',
            'date',
        )

    panels = [
        AutocompletePanel('collection'),
        FieldPanel('date'),
        FieldPanel('year'),
        FieldPanel('month'),
        FieldPanel('found_log_files'),
        FieldPanel('expected_log_files'),
        FieldPanel('status'),
    ]


class LogFile(CommonControlField):
    hash = models.CharField(_("Hash MD5"), max_length=32, null=True, blank=True, unique=True)

    path = models.CharField(_("Name"), max_length=255, null=False, blank=False)

    stat_result = models.JSONField(_("OS Stat Result"), null=False, blank=False)

    status = models.CharField(
        _("Status"), 
        choices=choices.LOG_FILE_STATUS, 
        max_length=3, 
        blank=False, 
        null=False,
    )

    collection = models.ForeignKey(
        Collection,
        verbose_name=_("Collection"),
        on_delete=models.DO_NOTHING,
        null=False,
        blank=False,
    )

    panels = [
        FieldPanel('hash'),
        FieldPanel('path'),
        FieldPanel('stat_result'),
        FieldPanel('status'),
        AutocompletePanel('collection'),
    ]

    base_form_class = CoreAdminModelForm

    class Meta:
        verbose_name = _("Log File")
        verbose_name_plural = _("Log Files")

    @classmethod
    def get(cls, hash):
        return cls.objects.get(hash=hash)

    @classmethod
    def create(cls, user, collection, path, stat_result, hash, status=None):
        try:
            return cls.get(hash=hash)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.created = timezone.now()
            obj.collection = collection
            obj.path = path
            obj.stat_result = stat_result
            obj.hash = hash
            obj.status = status or choices.LOG_FILE_STATUS_CREATED
            obj.save()
            return obj
        
    def __str__(self):
        return f'{self.path}'
