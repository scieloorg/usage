import os

from datetime import datetime

from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel

from core.models import CommonControlField

from .forms import Top100ArticlesFileForm


class Top100Articles(CommonControlField):
    pid_issn = models.CharField('PID ISSN', max_length=9, null=False, blank=False)
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
        FieldPanel('pid_issn'),
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
            'pid_issn',
            'pid',
            'year_month_day',
        )
        verbose_name_plural = _('Top 100 Articles')
        indexes = [
            models.Index(fields=['pid_issn']),
            models.Index(fields=['year_month_day']),
        ]

    @classmethod
    def create_or_update(cls, user, save=True, **data):
        defaults = {**data, 'updated_by': user, 'updated': datetime.utcnow()}
        obj, created = cls.objects.update_or_create(
            collection=data.get('collection'),
            pid_issn=data.get('pid_issn'),
            pid=data.get('pid'),
            year_month_day=data.get('year_month_day'),
            defaults=defaults
        )
        if created:
            obj.creator = user
            obj.created = datetime.utcnow()
        if save:
            obj.save()
        return obj, created
    
    @classmethod
    def bulk_create(cls, objects, ignore_conflicts=False):
        cls.objects.bulk_create(objs=objects, ignore_conflicts=ignore_conflicts)

    @classmethod
    def bulk_update(cls, objects, fields=['print_issn', 'online_issn', 'yop', 'total_item_requests', 'total_item_investigations', 'unique_item_requests', 'unique_item_investigations', 'updated', 'updated_by']):
        cls.objects.bulk_update(objs=objects, fields=fields)

    def __str__(self):
        return f'{self.pid_issn}, {self.pid}, {self.total_item_requests}'


class Top100ArticlesFile(CommonControlField):
    class Meta:
        verbose_name_plural = _("Top 100 Articles Files")
        verbose_name = _("Top 100 Articles File")

    class Status(models.TextChoices):
        QUEUED = "QUE", _("Queued")
        PARSING = "PAR", _("Parsing")
        PROCESSED = "PRO", _("Processed")
        INVALIDATED = "INV", _("Invalidated")
    
    attachment = models.ForeignKey(
        "wagtaildocs.Document",
        verbose_name=_("Attachment"),
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    status = models.CharField(max_length=5, choices=Status.choices, default=Status.QUEUED)

    def get_status_display(self):
        return self.Status(self.status).label
    
    get_status_display.admin_order_field = "status"
    get_status_display.short_description = "Status"

    @property
    def filename(self):
        if self.attachment:
            return os.path.basename(self.attachment.filename)
        return _('File not available')

    panels = [
        FieldPanel("attachment"),
        FieldPanel("status"),
    ]
    
    base_form_class = Top100ArticlesFileForm

    def __str__(self):
        return f'{self.filename}'
