import logging

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.models import Orderable
from wagtailautocomplete.edit_handlers import AutocompletePanel

from collection.models import Collection
from core.models import CommonControlField


class LogManagerCollectionConfig(ClusterableModel, CommonControlField):
    collection = models.OneToOneField(
        Collection,
        verbose_name=_("Collection"),
        on_delete=models.CASCADE,
        related_name="log_manager_config",
    )
    sample_size = models.FloatField(
        verbose_name=_("Sample Size"),
        blank=False,
        null=False,
        default=0.1,
    )
    buffer_size = models.IntegerField(
        verbose_name=_("Buffer Size"),
        blank=False,
        null=False,
        default=2048,
    )
    expected_logs_per_day = models.IntegerField(
        verbose_name=_("Expected Logs Per Day"),
        default=1,
    )

    panels = [
        AutocompletePanel("collection"),
        FieldPanel("sample_size"),
        FieldPanel("buffer_size"),
        FieldPanel("expected_logs_per_day"),
        InlinePanel("directories", label=_("Directories")),
        InlinePanel("emails", label=_("Emails")),
    ]

    def __str__(self):
        return f"{self.collection.acron3} Config"

    class Meta:
        verbose_name = _("Log Manager Collection Config")
        verbose_name_plural = _("Log Manager Collection Configs")

    @classmethod
    def load(cls, data, user):
        for item in data:
            try:
                collection = Collection.objects.get(acron3=item.get("acronym"))
            except Collection.DoesNotExist:
                logging.warning(f'Collection {item.get("acronym")} not found.')
                continue

            cls.create_or_update(
                user=user,
                collection=collection,
                sample_size=item.get("sample_size", 0.1),
                buffer_size=item.get("buffer_size", 2048),
                expected_logs_per_day=item.get("quantity", 1),
            )

    @classmethod
    def create_or_update(
        cls,
        user,
        collection,
        sample_size,
        buffer_size,
        expected_logs_per_day,
    ):
        obj, created = cls.objects.get_or_create(collection=collection)
        if created:
            obj.creator = user
            obj.created = timezone.now()

        obj.updated_by = user
        obj.updated = timezone.now()
        obj.sample_size = sample_size
        obj.buffer_size = buffer_size
        obj.expected_logs_per_day = expected_logs_per_day
        obj.save()
        logging.info(f"Config for {collection.acron3} updated.")
        return obj


class CollectionLogDirectory(Orderable, CommonControlField):
    config = ParentalKey(
        "LogManagerCollectionConfig",
        related_name="directories",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    path = models.CharField(
        verbose_name=_("Path"),
        max_length=255,
        blank=False,
        null=False,
    )
    directory_name = models.CharField(
        verbose_name=_("Directory Name"),
        max_length=255,
        blank=True,
        null=True,
    )
    active = models.BooleanField(
        verbose_name=_("Active"),
        default=True,
    )
    translator_class = models.CharField(
        verbose_name=_("URL Translator Class"),
        blank=False,
        null=False,
        default="classic",
    )

    def __str__(self):
        return f"{self.config.collection} - {self.path} - {self.directory_name}"

    @classmethod
    def load(cls, data, user):
        for item in data:
            try:
                collection = Collection.objects.get(acron3=item.get("acronym"))
                config, _ = LogManagerCollectionConfig.objects.get_or_create(
                    collection=collection
                )
            except Collection.DoesNotExist:
                logging.warning(f'Collection {item.get("acronym")} not found.')
                continue

            logging.info(item)
            cls.create_or_update(
                user=user,
                config=config,
                directory_name=item.get("directory_name"),
                path=item.get("path"),
                active=item.get("active", True),
                translator_class=item.get("translator_class", "classic"),
            )

    @classmethod
    def create_or_update(
        cls,
        user,
        config,
        directory_name,
        path,
        active,
        translator_class="classic",
    ):
        try:
            obj = cls.objects.get(config=config, path=path)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.created = timezone.now()
            obj.config = config

        obj.updated_by = user
        obj.updated = timezone.now()
        obj.directory_name = directory_name
        obj.path = path
        obj.active = active
        obj.translator_class = translator_class or "classic"

        obj.save()
        logging.info(f"{config.collection.acron3} - {directory_name} - {path}")
        return obj

    class Meta:
        verbose_name = _("Collection Log Directory")
        verbose_name_plural = _("Collection Log Directories")
        constraints = [
            models.UniqueConstraint(
                fields=["config", "path"], name="unique_config_path"
            )
        ]


class CollectionEmail(Orderable, CommonControlField):
    config = ParentalKey(
        "LogManagerCollectionConfig",
        related_name="emails",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
        blank=True,
        null=True,
    )
    position = models.CharField(
        verbose_name=_("Position"),
        max_length=255,
        blank=True,
        null=True,
    )
    email = models.EmailField(
        verbose_name=_("E-mail"),
        blank=False,
        null=False,
    )
    active = models.BooleanField(
        verbose_name=_("Active"),
        default=True,
    )

    def __str__(self):
        return f"{self.email} - {self.name}"

    @classmethod
    def load(cls, data, user):
        for item in data:
            try:
                collection = Collection.objects.get(acron3=item.get("acronym"))
                config, _ = LogManagerCollectionConfig.objects.get_or_create(
                    collection=collection
                )
            except Collection.DoesNotExist:
                logging.warning(f'Collection {item.get("acronym")} not found.')
                continue

            logging.info(item)
            cls.create_or_update(
                user=user,
                config=config,
                email=item.get("e-mail"),
                name=item.get("name"),
                position=item.get("position"),
                active=item.get("active", True),
            )

    @classmethod
    def create_or_update(
        cls,
        user,
        config,
        email,
        name,
        position,
        active,
    ):
        try:
            obj = cls.objects.get(config=config, email=email)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.created = timezone.now()
            obj.config = config
            obj.email = email

        obj.updated_by = user
        obj.updated = timezone.now()
        obj.name = name
        obj.position = position
        obj.active = active

        obj.save()
        logging.info(f"{config.collection.acron3} - {name} - {position} - {email}")
        return obj

    class Meta:
        verbose_name = _("Collection Email")
        verbose_name_plural = _("Collection Emails")
        constraints = [
            models.UniqueConstraint(
                fields=["config", "email"], name="unique_config_email"
            )
        ]
