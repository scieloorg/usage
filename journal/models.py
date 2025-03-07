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

    publisher_name = models.JSONField(
        verbose_name=_('Publisher Name'),
        blank=True,
        null=True,
        default=list,
    )

    subject_areas = models.JSONField(
        verbose_name=_('Subject Areas (CAPES)'),
        null=False,
        blank=False,
        default=list,
    )

    wos_subject_areas = models.JSONField(
        verbose_name=_('Subject Areas (WoS)'),
        null=False,
        blank=False,
        default=list,
    )

    def __str__(self):
        return f'{self.collection.acron2} - {self.scielo_issn} - {self.acronym}'

    @classmethod
    def metadata(cls, collection=None):
        objs = cls.objects.all() if not collection else cls.objects.filter(collection=collection)
        for j in objs:
            yield {
                'acronym': j.acronym,
                'collection': j.collection.acron3,
                'issns': j.issns,
                'publisher_name': j.publisher_name,
                'scielo_issn': j.scielo_issn,
                'subject_areas': j.subject_areas,
                'title': j.title,
                'wos_subject_areas': j.wos_subject_areas,
            }

    class Meta:
        verbose_name = _('Journal')
        verbose_name_plural = _('Journals')
        unique_together = (
            'collection',
            'scielo_issn', 
            'acronym',
        )
