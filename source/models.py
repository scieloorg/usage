from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from collection.models import Collection
from core.models import CommonControlField

METADATA_ITERATOR_CHUNK_SIZE = 2000


class Source(CommonControlField):
    SOURCE_TYPE_JOURNAL = "journal"
    SOURCE_TYPE_BOOK = "book"
    SOURCE_TYPE_PREPRINT_SERVER = "preprint_server"
    SOURCE_TYPE_DATA_REPOSITORY = "data_repository"
    SOURCE_TYPE_OTHER = "other"
    SOURCE_TYPE_CHOICES = (
        (SOURCE_TYPE_JOURNAL, _("Journal")),
        (SOURCE_TYPE_BOOK, _("Book")),
        (SOURCE_TYPE_PREPRINT_SERVER, _("Preprint Server")),
        (SOURCE_TYPE_DATA_REPOSITORY, _("Data Repository")),
        (SOURCE_TYPE_OTHER, _("Other")),
    )

    ACCESS_TYPE_OPEN_ACCESS = "open_access"
    ACCESS_TYPE_COMMERCIAL = "commercial"
    ACCESS_TYPE_CHOICES = (
        (ACCESS_TYPE_OPEN_ACCESS, _("Open Access")),
        (ACCESS_TYPE_COMMERCIAL, _("Commercial")),
    )

    collection = models.ForeignKey(
        Collection,
        verbose_name=_("Collection"),
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        db_index=True,
    )

    source_type = models.CharField(
        verbose_name=_("Source Type"),
        max_length=32,
        choices=SOURCE_TYPE_CHOICES,
        blank=False,
        null=False,
        db_index=True,
    )

    source_id = models.CharField(
        verbose_name=_("Source ID"),
        max_length=255,
        blank=False,
        null=False,
        db_index=True,
    )

    scielo_issn = models.CharField(
        verbose_name=_("SciELO ISSN"),
        max_length=9,
        blank=True,
        null=True,
        db_index=True,
    )

    acronym = models.CharField(
        verbose_name=_("Source Acronym"),
        max_length=64,
        blank=True,
        null=True,
        default="",
    )

    title = models.CharField(
        verbose_name=_("Source Title"),
        max_length=500,
        blank=False,
        null=False,
    )

    identifiers = models.JSONField(
        verbose_name=_("Identifiers"),
        null=True,
        blank=True,
        default=dict,
    )

    publisher_name = models.JSONField(
        verbose_name=_("Publisher Name"),
        blank=True,
        null=True,
        default=list,
    )

    subject_areas = models.JSONField(
        verbose_name=_("Subject Areas (CAPES)"),
        null=False,
        blank=False,
        default=list,
    )

    wos_subject_areas = models.JSONField(
        verbose_name=_("Subject Areas (WoS)"),
        null=False,
        blank=False,
        default=list,
    )

    default_lang = models.CharField(
        verbose_name=_("Default Language"),
        max_length=8,
        blank=True,
        null=True,
    )

    publication_date = models.CharField(
        verbose_name=_("Publication Date"),
        max_length=32,
        blank=True,
        null=True,
    )

    publication_year = models.CharField(
        verbose_name=_("Publication Year"),
        max_length=4,
        blank=True,
        null=True,
        db_index=True,
    )

    access_type = models.CharField(
        verbose_name=_("Access Type"),
        max_length=32,
        choices=ACCESS_TYPE_CHOICES,
        blank=True,
        null=True,
        db_index=True,
    )

    extra_data = models.JSONField(
        verbose_name=_("Extra Data"),
        null=True,
        blank=True,
        default=dict,
    )

    def __str__(self):
        return f"{self.collection.acron3} - {self.source_type} - {self.source_id}"

    @classmethod
    def delete_book_source_by_id(cls, collection, book_id):
        return cls.objects.filter(
            collection=collection,
            source_type=cls.SOURCE_TYPE_BOOK,
            source_id=str(book_id),
        ).delete()

    @classmethod
    def find_journal_by_issns(cls, collection, issns):
        for issn in filter(None, issns or []):
            source = (
                cls.objects.filter(
                    collection=collection,
                    source_type=cls.SOURCE_TYPE_JOURNAL,
                )
                .filter(
                    Q(scielo_issn=issn)
                    | Q(source_id=issn)
                    | Q(identifiers__electronic_issn=issn)
                    | Q(identifiers__print_issn=issn)
                    | Q(identifiers__scielo_issn=issn)
                )
                .first()
            )
            if source:
                return source
        return None

    @classmethod
    def find_journal_by_acronym(cls, collection, acronym):
        if not acronym:
            return None

        return cls.objects.filter(
            collection=collection,
            source_type=cls.SOURCE_TYPE_JOURNAL,
            acronym=acronym,
        ).first()

    @staticmethod
    def _extract_issns(identifiers):
        if not isinstance(identifiers, dict):
            return set()

        return {
            value
            for key, value in identifiers.items()
            if value and "issn" in str(key).lower()
        }

    @classmethod
    def metadata(cls, collection=None):
        queryset = cls.objects.all()
        if collection:
            queryset = queryset.filter(collection=collection)

        queryset = queryset.values(
            "acronym",
            "default_lang",
            "extra_data",
            "identifiers",
            "publication_date",
            "publication_year",
            "access_type",
            "publisher_name",
            "scielo_issn",
            "source_id",
            "source_type",
            "subject_areas",
            "title",
            "wos_subject_areas",
            collection_acron3=models.F("collection__acron3"),
        )

        for source in queryset.iterator(chunk_size=METADATA_ITERATOR_CHUNK_SIZE):
            identifiers = source["identifiers"] or {}
            yield {
                "acronym": source["acronym"],
                "collection": source["collection_acron3"],
                "default_lang": source["default_lang"],
                "extra_data": source["extra_data"] or {},
                "identifiers": identifiers,
                "issns": cls._extract_issns(identifiers),
                "publication_date": source["publication_date"],
                "publication_year": source["publication_year"],
                "access_type": source["access_type"],
                "publisher_name": source["publisher_name"] or [],
                "scielo_issn": source["scielo_issn"],
                "source_id": source["source_id"],
                "source_type": source["source_type"],
                "subject_areas": source["subject_areas"] or [],
                "title": source["title"],
                "wos_subject_areas": source["wos_subject_areas"] or [],
            }

    class Meta:
        verbose_name = _("Source")
        verbose_name_plural = _("Sources")
        unique_together = (
            "collection",
            "source_type",
            "source_id",
        )
        indexes = [
            models.Index(
                fields=["collection", "source_type"],
                name="source_collection_type_idx",
            ),
            models.Index(
                fields=["collection", "scielo_issn"],
                name="source_collection_issn_idx",
            ),
        ]
