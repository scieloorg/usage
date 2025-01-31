from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import CommonControlField
from collection.models import Collection


class Article(CommonControlField):
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

    pid_v2 = models.CharField(
        verbose_name=_('PID V2'),
        max_length=23,
        blank=False,
        null=False,
    )

    pid_v3 = models.CharField(
        verbose_name=_('PID V3'),
        max_length=23,
        blank=True,
        null=True,
    )

    pdfs = models.JSONField(
        verbose_name=_('Format with Language'),
        null=True,
        blank=True,
        default=dict,
    )

    default_lang = models.CharField(
        verbose_name=_('Default Language'),
        max_length=2,
        blank=False,
        null=False,
    )

    text_langs = models.JSONField(
        verbose_name=_('Text Languages'),
        null=True,
        blank=True,
        default=dict,
    )

    processing_date = models.CharField(
        verbose_name=_('Processing Date'), 
        max_length=32,
        null=False,
        blank=False,
    )

    publication_date = models.CharField(
        verbose_name=_('Publication Date'), 
        max_length=32,
        null=False,
        blank=False,
    )

    publication_year = models.CharField(
        verbose_name=_('Publication Year'), 
        max_length=4,
        null=False,
        blank=False,
    )

    def __str__(self):
        return f'{self.collection.acron2} - {self.scielo_issn} - {self.pid_v2}'
    
    class Meta:
        verbose_name = _('Article')
        verbose_name_plural = _('Articles')
        unique_together = (
            'collection',
            'scielo_issn', 
            'pid_v2',
            'pid_v3',
        )
