import hashlib

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import CommonControlField


class RobotUserAgent(CommonControlField):
    pattern = models.CharField(
        verbose_name=_('Pattern'),
        max_length=255,
        null=False,
        blank=False,
        primary_key=True,
    )
    last_changed = models.DateField(
        verbose_name=_('Last Changed'),
        null=False,
        blank=False,
    )

    @classmethod
    def get_all_patterns(cls):
        return cls.objects.values_list('pattern', flat=True)

    def __str__(self):
        return self.pattern


class MMDB(CommonControlField):
    id = models.CharField(
        verbose_name=_('ID (HASH)'),
        max_length=64, 
        primary_key=True,
    )
    data = models.BinaryField(
        verbose_name=_('MMDB Data'),
    )
    url = models.URLField(
        verbose_name=_('URL'),
        max_length=255,
        null=True,
        blank=True,
    )
    
    def save(self, *args, **kwargs):
        if self.data:
            self.id = MMDB.compute_hash(self.data)
        super().save(*args, **kwargs)

    @classmethod
    def compute_hash(cls, data):
        return hashlib.sha256(data).hexdigest()

    def __str__(self):
        return f'{self.id}'
