from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import CommonControlField
from collection.models import Collection


class Journal(CommonControlField):
    collection = models.ForeignKey(
        Collection,
        verbose_name=_('Collection'),
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    scielo_issn = models.CharField(
        verbose_name=_('SciELO ISSN'),
        max_length=9,
        blank=False,
        null=False,
    )

    issns = models.JSONField(
        verbose_name=_('ISSNs'),
        null=True,
        blank=True,
        default=dict,
    )
    
    acronym = models.CharField(
        verbose_name=_('Journal Acronym'),
        max_length=32,
        blank=True,
        null=True,
        default='',
    )

    title = models.CharField(
        verbose_name=_('Journal Title'),
        max_length=255,
        blank=False,
        null=False,
    )

    def __str__(self):
        return f'{self.collection.acron2} - {self.scielo_issn} - {self.acronym}'
    
    class Meta:
        verbose_name = _('Journal')
        verbose_name_plural = _('Journals')
        unique_together = (
            'collection',
            'scielo_issn', 
            'acronym',
        )
