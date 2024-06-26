from datetime import datetime

from django.db import models
from django.db.utils import IntegrityError
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel

from core.models import CommonControlField


class Top100Articles(CommonControlField):
    key_issn = models.CharField('Key ISSN', max_length=9, null=False, blank=False)
    year_month_day = models.DateField('Date of access', null=False, blank=False)

    print_issn = models.CharField('Print ISSN', max_length=9, null=True, blank=True)
    online_issn = models.CharField('Online ISSN', max_length=9, null=True, blank=True)

    collection = models.CharField('Collection Acronym 3', max_length=3, null=False, blank=False)
    pid = models.CharField('Publication ID', null=False, blank=False)
    yop = models.PositiveSmallIntegerField('Year of Publication', null=False, blank=False)
    
    total_item_requests = models.IntegerField('Total Item Requests', null=False, blank=False)
    total_item_investigations = models.IntegerField('Total Item Investigations', null=False, blank=False)
    unique_item_requests = models.IntegerField('Unique Item Requests', null=False, blank=False)
    unique_item_investigations = models.IntegerField('Unique Item Investigations', null=False, blank=False)

    panels = [
        FieldPanel('key_issn'),
        FieldPanel('year_month_day'),
        FieldPanel('print_issn'),
        FieldPanel('online_issn'),
        FieldPanel('collection'),
        FieldPanel('pid'),
        FieldPanel('yop'),
        FieldPanel('total_item_requests'),
        FieldPanel('total_item_investigations'),
        FieldPanel('unique_item_requests'),
        FieldPanel('unique_item_investigations'),
    ]

    class Meta:
        unique_together = (
            'collection',
            'key_issn',
            'pid',
            'year_month_day',
        )
        verbose_name = _('Top 100 Articles')
        indexes = [
            models.Index(fields=['key_issn']),
            models.Index(fields=['year_month_day']),
        ]

    @classmethod
    def create(
        cls, 
        user, 
        key_issn, 
        year_month_day, 
        print_issn, 
        online_issn, 
        collection, 
        pid, 
        yop, 
        total_item_requests, 
        total_item_investigations, 
        unique_item_requests, 
        unique_item_investigations,
    ):
        obj = cls()
        obj.creator = user
        obj.created = datetime.utcnow()
        
        obj.key_issn = key_issn
        obj.year_month_day = year_month_day
        obj.print_issn = print_issn
        obj.online_issn = online_issn
        obj.collection = collection
        obj.pid = pid
        obj.yop = yop
        obj.total_item_requests = total_item_requests
        obj.total_item_investigations = total_item_investigations
        obj.unique_item_requests = unique_item_requests
        obj.unique_item_investigations = unique_item_investigations

        try:
            obj.save()
            return obj
        except IntegrityError:
            raise

    def __str__(self):
        return f'{self.key_issn}, {self.pid}, {self.total_item_requests}'
