import hashlib

from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel


class RobotUserAgent(models.Model):
    SOURCE_ALL = "all"
    SOURCE_COUNTER = "counter"
    SOURCE_SCIELO = "scielo"
    SOURCE_CHOICES = [SOURCE_ALL, SOURCE_COUNTER, SOURCE_SCIELO]

    panels = [
        FieldPanel("pattern"),
        FieldPanel("source_counter"),
        FieldPanel("source_scielo"),
        FieldPanel("is_active"),
        FieldPanel("source_url"),
        FieldPanel("last_changed"),
    ]

    created = models.DateTimeField(verbose_name=_("Creation date"), auto_now_add=True)
    updated = models.DateTimeField(verbose_name=_("Last update date"), auto_now=True)

    pattern = models.CharField(
        verbose_name=_("Pattern"),
        max_length=255,
        null=False,
        blank=False,
        primary_key=True,
    )
    source_counter = models.BooleanField(
        verbose_name=_("From Atmire/COUNTER"),
        default=False,
        db_index=True,
    )
    source_scielo = models.BooleanField(
        verbose_name=_("From SciELO"),
        default=False,
        db_index=True,
    )
    is_active = models.BooleanField(
        verbose_name=_("Active"),
        default=True,
        db_index=True,
    )
    source_url = models.URLField(
        verbose_name=_("Source URL"),
        max_length=255,
        null=True,
        blank=True,
    )
    last_changed = models.DateField(
        verbose_name=_("Last Changed"),
        null=True,
        blank=True,
    )

    @classmethod
    def get_all_patterns(cls):
        return cls.get_patterns(source=cls.SOURCE_ALL)

    @classmethod
    def normalize_source(cls, source=None):
        normalized = (source or cls.SOURCE_ALL).lower()
        if normalized not in cls.SOURCE_CHOICES:
            raise ValueError(f"Unsupported robots source: {source}")
        return normalized

    @classmethod
    def get_patterns(cls, source=None):
        source = cls.normalize_source(source)
        queryset = cls.objects.filter(is_active=True)

        if source == cls.SOURCE_COUNTER:
            queryset = queryset.filter(source_counter=True)
        elif source == cls.SOURCE_SCIELO:
            queryset = queryset.filter(source_scielo=True)

        return queryset.values_list("pattern", flat=True)

    @property
    def source_labels(self):
        labels = []
        if self.source_counter:
            labels.append("Atmire/COUNTER")
        if self.source_scielo:
            labels.append("SciELO")
        return ", ".join(labels) or "-"

    def save(self, *args, **kwargs):
        if not self.source_counter and not self.source_scielo:
            self.source_scielo = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.pattern


class MMDB(models.Model):
    created = models.DateTimeField(verbose_name=_("Creation date"), auto_now_add=True)
    updated = models.DateTimeField(verbose_name=_("Last update date"), auto_now=True)
    id = models.CharField(
        verbose_name=_("ID (HASH)"),
        max_length=64,
        primary_key=True,
    )
    data = models.BinaryField(
        verbose_name=_("MMDB Data"),
    )
    url = models.URLField(
        verbose_name=_("URL"),
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
        return f"{self.id}"
