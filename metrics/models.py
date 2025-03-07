from django.db import models
from django.utils.translation import gettext_lazy as _

from collection.models import Collection
from journal.models import Journal
from article.models import Article


class Item(models.Model):
    collection = models.ForeignKey(
        Collection,
        verbose_name=_("Collection"),
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        db_index=True,
    )
    
    journal = models.ForeignKey(
        Journal,
        verbose_name=_("Journal"),
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        db_index=True,
    )
    
    article = models.ForeignKey(
        Article,
        verbose_name=_("Article"),
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        db_index=True,
    )

    def __str__(self):
        return '|'.join([
            self.collection.acron2,
            self.journal.acronym,
            self.article.pid_v2,
        ])
    
    class Meta:
        verbose_name = _("Item")
        verbose_name_plural = _("Items")
        indexes = [
            models.Index(fields=['collection', 'journal', 'article']),
            models.Index(fields=['collection', 'journal']),
        ]
        unique_together = (
            'collection',
            'journal',
            'article',
        )


class UserAgent(models.Model):
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
        null=False,
        blank=False,
        db_index=True,
    )

    version = models.CharField(
        verbose_name=_("Version"),
        max_length=255,
        null=False,
        blank=False,
        db_index=True,
    )

    def __str__(self):
        return f"{self.name} {self.version}"

    class Meta:
        verbose_name = _("User Agent")
        verbose_name_plural = _("User Agents")
        unique_together = (
            'name',
            'version',
        )


class UserSession(models.Model):
    datetime = models.DateTimeField(
        verbose_name=_("Datetime"),
        null=False,
        blank=False,
    )

    user_agent = models.ForeignKey(
        UserAgent,
        verbose_name=_("User Agent"),
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        db_index=True,
    )

    user_ip = models.CharField(
        verbose_name=_("User IP"),
        max_length=255,
        null=False,
        blank=False,
        db_index=True,
    )

    def user_session(self):
        return '|'.join([
            self.user_agent.name,
            self.user_agent.version,
            self.user_ip,
            self.datetime.strftime('%Y-%m-%d'),
            self.datetime.strftime('%H'),
        ])

    def __str__(self):
        return self.user_session()

    class Meta:
        verbose_name = _("User Session")
        verbose_name_plural = _("User Sessions")
        unique_together = (
            'datetime',
            'user_agent',
            'user_ip',
        )


class ItemAccess(models.Model):
    item = models.ForeignKey(
        'Item',
        verbose_name=_("Item"),
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        db_index=True,
    )

    user_session = models.ForeignKey(
        'UserSession',
        verbose_name=_("User Session"),
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        db_index=True,
    )
 
    country_code = models.CharField(
        verbose_name=_("Country"),
        max_length=2,
        null=False,
        blank=False,
        db_index=True,
    )

    media_language = models.CharField(
        verbose_name=_("Media Language"),
        max_length=2,
        null=False,
        blank=False,
        db_index=True,
    )

    media_format = models.CharField(
        verbose_name=_("Media Format"),
        max_length=10,
        null=False,
        blank=False,
    )

    class Meta:
        verbose_name = _("Item Access")
        verbose_name_plural = _("Items Access")
        unique_together = (
            'item',
            'user_session',
            'country_code',
            'media_format',
            'media_language',
        )
