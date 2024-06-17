from datetime import datetime

from django.db import models
from django.db.models import Q
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtailautocomplete.edit_handlers import AutocompletePanel

from collection.models import Collection
from core.forms import CoreAdminModelForm
from core.models import CommonControlField
from tracker.models import UnexpectedEvent

from . import choices
from .exceptions import (
    LogFileAlreadyExistsError, 
    MultipleCollectionConfigError,
    UndefinedCollectionConfigError,
)


class ApplicationConfig(CommonControlField):
    config_type = models.CharField(
        verbose_name=_('Config Type'),
        choices=choices.APLLICATION_CONFIG_TYPE,
        max_length=3,
        null=False,
        blank=False,
    )

    value = models.CharField(
        verbose_name=_("Value"),
        max_length=255, 
        null=False, 
        blank=False,
    )

    is_enabled = models.BooleanField(
        verbose_name=_("Enabled"),
        default=True,
    )

    version_number = models.IntegerField(
        verbose_name=_("Version Number"),
        null=False,
        blank=False,
    )

    base_form_class = CoreAdminModelForm

    panels = [
        FieldPanel('config_type'),
        FieldPanel('value'),
        FieldPanel('is_enabled'),
        FieldPanel('version_number'),
    ]

    class Meta:
        ordering = ['value']
        unique_together = ('config_type', 'value', 'version_number',)
        verbose_name = _("Application Config")
        verbose_name_plural = _("Application Configs")

    @classmethod
    def filter_by_config_type(cls, config_type, sorting_field='-version_number'):
        return cls.objects.filter(
            config_type=config_type,
        ).order_by(sorting_field).first()
    
    @classmethod
    def get_field_values(cls, config_type):
        return [i.value for i in cls.objects.filter(config_type=config_type)]
    
    @classmethod
    def create(cls, user, config_type, value, is_enabled=True, version_number=None):
        last_config = cls.objects.filter(config_type=config_type).order_by('-version_number').first()
        if last_config is not None:
            last_version_number = last_config.version_number
        else:
            last_version_number = 0

        obj = cls()
        obj.creator = user
        obj.created = datetime.utcnow()
        obj.config_type = config_type
        obj.value = value
        obj.is_enabled = is_enabled
        obj.version_number = version_number or last_version_number + 1
        obj.save()

        return obj
    
    def __str__(self):
        return f'{self.value}'


class CollectionConfig(CommonControlField):
    collection = models.ForeignKey(
        Collection, 
        verbose_name=_('Collection'), 
        on_delete=models.DO_NOTHING, 
        null=False, 
        blank=False,
    )

    config_type = models.CharField(
        verbose_name=_('Type'),
        choices=choices.COLLECTION_CONFIG_TYPE,
        max_length=3,
        null=False,
        blank=False,
    )

    value = models.CharField(
        verbose_name=_("Value"),
        max_length=255, 
        null=False, 
        blank=False,
    )

    is_enabled = models.BooleanField(
        verbose_name=_("Enabled"),
        default=True,
    )

    start_date = models.DateField(
        verbose_name=_('Start Date'),
        null=False,
        blank=False,
    )

    end_date = models.DateField(
        verbose_name=_("End Date"),
        null=True,
        blank=True
    )

    base_form_class = CoreAdminModelForm

    panels = [
        AutocompletePanel('collection'),
        FieldPanel('config_type'),
        FieldPanel('value'),
        FieldPanel('start_date'),
        FieldPanel('end_date'),
        FieldPanel('is_enabled'),
    ]

    class Meta:
        ordering = ['collection', 'value']
        unique_together = ('collection', 'config_type', 'start_date', 'end_date', 'value',)
        verbose_name = _("Collection Configuration")
        verbose_name_plural = _("Collection Configurations")

    @classmethod
    def filter_by_collection_and_config_type(cls, collection_acron2, config_type, is_enabled=True):
        return cls.objects.filter(
            collection__acron2=collection_acron2, 
            config_type=config_type, 
            is_enabled=is_enabled
        )
        
    @classmethod
    def get_number_of_expected_files_by_day(cls, collection_acron2, date, is_enabled=True):
        files_by_day = cls.objects.filter(
            Q(collection__acron2=collection_acron2) &
            Q(start_date__lte=date) &
            (Q(end_date__gte=date) | Q(end_date__isnull=True)) &
            Q(config_type=choices.COLLECTION_CONFIG_TYPE_FILES_PER_DAY) &
            Q(is_enabled=is_enabled)
        )

        if files_by_day.count() > 1:
            raise MultipleCollectionConfigError("ERROR. Please, keep only one configuration enabled for the FILES_BY_DAY attribute.")

        if files_by_day.count() == 0:
            raise UndefinedCollectionConfigError("ERROR. Please, add an Application Configuration for the FILES_BY_DAY attribute.")
        
        return int(files_by_day.get().value)
    
    def __str__(self):
        return f'{self.value}'


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
    def create(cls, user, log_file, date):
        obj = cls()

        obj.creator = user
        obj.created = datetime.utcnow()
        obj.log_file = log_file
        obj.date = date
        obj.save()
        
        return obj
    
    @classmethod
    def filter_by_collection_and_date(cls, collection_acron2, date):
        return cls.objects.filter(
            ~Q(log_file__status__in=[
                choices.LOG_FILE_STATUS_CREATED, 
                choices.LOG_FILE_STATUS_INVALIDATED
            ]),
            log_file__collection__acron2=collection_acron2,
            date=date,
        )
        
    @classmethod
    def get_number_of_existing_files_for_date(cls, collection_acron2, date):
        return cls.objects.filter(
            ~Q(log_file__status__in=[
                choices.LOG_FILE_STATUS_CREATED, 
                choices.LOG_FILE_STATUS_INVALIDATED
            ]),
            log_file__collection__acron2=collection_acron2,
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
        max_length=4,
        null=False,
        blank=False,
    )
    
    month = models.IntegerField(
        _('Month'),
        max_length=2,
        null=False,
        blank=False,
    )

    found_log_files = models.IntegerField(
        verbose_name=_('Number of Found Valid Log Files'), 
        max_length=8,
        default=0,
    )

    expected_log_files = models.IntegerField(
        verbose_name=_('Number of Expected Valid Log Files'),
        max_length=8,
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
            obj.updated = datetime.utcnow()
        else:
            obj.creator = user
            obj.created = datetime.utcnow()

        obj.expected_log_files = expected_log_files            
        obj.found_log_files = found_log_files
        
        if found_log_files < expected_log_files:
            obj.status = choices.COLLECTION_LOG_FILE_DATE_COUNT_MISSING_FILES
        elif found_log_files > expected_log_files:
            obj.status = choices.COLLECTION_LOG_FILE_DATE_COUNT_EXTRA_FILES
        else:
            obj.status = choices.COLLECTION_LOG_FILE_DATE_COUNT_OK 
        
        try:
            obj.save()
            return obj        
        except IntegrityError:
            ...
    
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
            obj = cls.get(hash=hash)
            UnexpectedEvent.create(
                LogFileAlreadyExistsError,
                detail={
                    'Error': _('File hash is already registered.'),
                    'Action': _('No action required from the user.'),
                    'Result': _('The file has been ignored.'),
                    'Hash': hash,
                })
            return 
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.created = datetime.utcnow()
            obj.collection = collection
            obj.path = path
            obj.stat_result = stat_result
            obj.hash = hash
            obj.status = status or choices.LOG_FILE_STATUS_CREATED
            obj.save()
            return obj
        
    def __str__(self):
        return f'{self.path}'


class LogProcessedRow(CommonControlField):
    log_file = models.ForeignKey(
        LogFile,
        verbose_name=_("LogFile"),
        on_delete=models.DO_NOTHING,
        null=False,
        blank=False,
    )
    server_time = models.DateTimeField(_("Server Time"), null=False, blank=False)
    browser_name = models.CharField(_("Browser Name"), null=False, blank=False)
    browser_version = models.CharField(_("Browser Version"), null=False, blank=False)
    ip = models.CharField(_("IP"), null=False, blank=False)
    latitude = models.FloatField(_("Latitude"), null=False, blank=False)
    longitude = models.FloatField(_("Longitude"), null=False, blank=False)
    action_name = models.CharField(_("Action Name"), null=False, blank=False)

    base_form_class = CoreAdminModelForm

    panels = [
        AutocompletePanel('log_file'),
        FieldPanel('server_time'),
        FieldPanel('browser_name'),
        FieldPanel('browser_version'),
        FieldPanel('ip'),
        FieldPanel('latitude'),
        FieldPanel('longitude'),
        FieldPanel('action_name'),
    ]

    class Meta:
        unique_together = (
            'server_time',
            'browser_name', 
            'browser_version',
            'ip',
            'latitude',
            'longitude',
            'action_name',
        )
        verbose_name = _("Log Processed Row")
        verbose_name_plural = _("Log Processed Rows")
        indexes = [
            models.Index(fields=['server_time']),
            models.Index(fields=['browser_name']),
            models.Index(fields=['browser_version']),
            models.Index(fields=['ip']),
            models.Index(fields=['latitude']),
            models.Index(fields=['longitude']),
            models.Index(fields=['action_name']),
        ]

    @classmethod
    def create(cls, user, log_file, server_time, browser_name, browser_version, ip, latitude, longitude, action_name):
        obj = cls()
        obj.creator = user
        obj.created = datetime.utcnow()

        obj.log_file = log_file
        obj.server_time = server_time
        obj.browser_name = browser_name
        obj.browser_version = browser_version
        obj.ip = ip
        obj.latitude = latitude
        obj.longitude = longitude
        obj.action_name = action_name
    
        try:
            obj.save()
            return obj        
        except IntegrityError:
            ...

    def __str__(self):
        return f'{self.action_name}'
