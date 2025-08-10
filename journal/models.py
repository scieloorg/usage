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
        db_index=True,
    )

    scielo_issn = models.CharField(
        verbose_name=_('SciELO ISSN'),
        max_length=9,
        blank=False,
        null=False,
        db_index=True,
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
        queryset = cls.objects.all()
        if collection:
            queryset = queryset.filter(collection=collection)

        for journal in queryset.only(
            'acronym', 'collection__acron3', 'issns', 'publisher_name',
            'scielo_issn', 'subject_areas', 'title', 'wos_subject_areas'
        ):
            yield {
                'acronym': journal.acronym,
                'collection': journal.collection.acron3,
                'issns': set([v for v in journal.issns.values() if v]),
                'publisher_name': journal.publisher_name,
                'scielo_issn': journal.scielo_issn,
                'subject_areas': journal.subject_areas,
                'title': journal.title,
                'wos_subject_areas': journal.wos_subject_areas,
            }

    class Meta:
        verbose_name = _('Journal')
        verbose_name_plural = _('Journals')
        unique_together = (
            'collection',
            'scielo_issn', 
            'acronym',
        )
