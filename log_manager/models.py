from datetime import datetime

from django.db import models
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel

from collection.models import Collection
from core.forms import CoreAdminModelForm
from core.models import CommonControlField
from tracker.models import UnexpectedEvent

from . import choices
from .exceptions import LogFileAlreadyExistsError


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
    def get(cls, config_type, sorting_field='-version_number'):
        return cls.objects.filter(
            config_type=config_type,
        ).order_by(sorting_field).first()
    
    @classmethod
    def get_field_values(cls, config_type):
        return [i.value for i in cls.objects.filter(config_type=config_type)]
    
    @classmethod
    def create(cls, user, config_type, value, is_enabled=True, version_number=None):
        try:
            last_config = cls.objects.filter(config_type=config_type).order_by('-version_number').first()
            last_version_number = last_config.version_number
        except cls.DoesNotExist:
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
