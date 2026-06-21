from django.db import models
from django.utils.translation import gettext_lazy as _

from collection.models import Collection
from core.models import CommonControlField
from source.models import Source


class Document(CommonControlField):
    DOCUMENT_TYPE_ARTICLE = "article"
    DOCUMENT_TYPE_PREPRINT = "preprint"
    DOCUMENT_TYPE_DATASET = "dataset"
    DOCUMENT_TYPE_BOOK = "book"
    DOCUMENT_TYPE_CHAPTER = "chapter"
    DOCUMENT_TYPE_OTHER = "other"
    DOCUMENT_TYPE_CHOICES = (
        (DOCUMENT_TYPE_ARTICLE, _("Article")),
        (DOCUMENT_TYPE_PREPRINT, _("Preprint")),
        (DOCUMENT_TYPE_DATASET, _("Dataset")),
        (DOCUMENT_TYPE_BOOK, _("Book")),
        (DOCUMENT_TYPE_CHAPTER, _("Chapter")),
        (DOCUMENT_TYPE_OTHER, _("Other")),
    )

    collection = models.ForeignKey(
        Collection,
        verbose_name=_("Collection"),
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        db_index=True,
    )

    source = models.ForeignKey(
        Source,
        verbose_name=_("Source"),
        on_delete=models.CASCADE,
        related_name="documents",
        blank=True,
        null=True,
        db_index=True,
    )

    parent_document = models.ForeignKey(
        "self",
        verbose_name=_("Parent Document"),
        on_delete=models.SET_NULL,
        related_name="child_documents",
        blank=True,
        null=True,
        db_index=True,
    )

    document_type = models.CharField(
        verbose_name=_("Document Type"),
        max_length=32,
        choices=DOCUMENT_TYPE_CHOICES,
        blank=False,
        null=False,
        db_index=True,
    )

    document_id = models.CharField(
        verbose_name=_("Document ID"),
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

    pid_v2 = models.CharField(
        verbose_name=_("PID V2"),
        max_length=23,
        blank=True,
        null=True,
        db_index=True,
    )

    pid_v3 = models.CharField(
        verbose_name=_("PID V3"),
        max_length=23,
        blank=True,
        null=True,
        db_index=True,
    )

    pid_generic = models.CharField(
        verbose_name=_("PID Generic"),
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
    )

    title = models.CharField(
        verbose_name=_("Document Title"),
        max_length=500,
        blank=True,
        null=True,
    )

    identifiers = models.JSONField(
        verbose_name=_("Identifiers"),
        null=True,
        blank=True,
        default=dict,
    )

    files = models.JSONField(
        verbose_name=_("Files"),
        null=True,
        blank=True,
        default=dict,
    )

    default_lang = models.CharField(
        verbose_name=_("Default Language"),
        max_length=8,
        blank=True,
        null=True,
    )

    text_langs = models.JSONField(
        verbose_name=_("Text Languages"),
        null=True,
        blank=True,
        default=list,
    )

    default_media_format = models.CharField(
        verbose_name=_("Default Media Format"),
        max_length=32,
        blank=True,
        null=True,
    )

    processing_date = models.CharField(
        verbose_name=_("Processing Date"),
        max_length=32,
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

    extra_data = models.JSONField(
        verbose_name=_("Extra Data"),
        null=True,
        blank=True,
        default=dict,
    )

    def __str__(self):
        return f"{self.collection.acron3} - {self.document_type} - {self.document_id}"

    @classmethod
    def build_book_pid_generic(cls, book_id):
        if book_id in (None, ""):
            return None
        return f"book:{book_id}"

    @classmethod
    def build_chapter_pid_generic(cls, book_id, chapter_id):
        if book_id in (None, "") or chapter_id in (None, ""):
            return None
        return f"book:{book_id}/chapter:{chapter_id}"

    @classmethod
    def find_by_identifiers(cls, collection, document_type, *identifiers):
        identifiers = [str(value) for value in identifiers if value not in (None, "")]
        if not identifiers:
            return None

        queryset = cls.objects.filter(
            collection=collection,
            document_type=document_type,
        )

        for field_name in ("document_id", "pid_v2", "pid_v3", "pid_generic"):
            for identifier in identifiers:
                document = queryset.filter(**{field_name: identifier}).first()
                if document:
                    return document

        return None

    @classmethod
    def book_exists_for_raw_id(cls, collection, raw_id):
        return cls.objects.filter(
            collection=collection,
            document_type=cls.DOCUMENT_TYPE_BOOK,
            extra_data__raw_id=str(raw_id),
        ).exists()

    @classmethod
    def delete_documents_by_raw_id(cls, collection, raw_id):
        return cls.objects.filter(
            collection=collection,
            extra_data__raw_id=str(raw_id),
        ).delete()

    @classmethod
    def metadata(cls, collection=None):
        queryset = cls.objects.select_related("collection", "source").only(
            "collection__acron3",
            "default_lang",
            "default_media_format",
            "document_id",
            "document_type",
            "extra_data",
            "files",
            "identifiers",
            "parent_document__document_id",
            "pid_generic",
            "pid_v2",
            "pid_v3",
            "processing_date",
            "publication_date",
            "publication_year",
            "scielo_issn",
            "source__scielo_issn",
            "source__source_id",
            "source__source_type",
            "text_langs",
            "title",
        )

        if collection:
            queryset = queryset.filter(collection=collection)

        for document in queryset.iterator():
            source = document.source
            yield {
                "collection": document.collection.acron3,
                "default_lang": document.default_lang,
                "default_media_format": document.default_media_format,
                "document_id": document.document_id,
                "document_type": document.document_type,
                "extra_data": document.extra_data or {},
                "files": document.files or {},
                "identifiers": document.identifiers or {},
                "parent_document_id": (
                    document.parent_document.document_id
                    if document.parent_document
                    else None
                ),
                "pid_generic": document.pid_generic,
                "pid_v2": document.pid_v2,
                "pid_v3": document.pid_v3,
                "processing_date": document.processing_date,
                "publication_date": document.publication_date,
                "publication_year": document.publication_year,
                "scielo_issn": document.scielo_issn
                or (source.scielo_issn if source else None),
                "source_id": source.source_id if source else None,
                "source_type": source.source_type if source else None,
                "text_langs": document.text_langs or [],
                "title": document.title,
            }

    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")
        unique_together = (
            "collection",
            "document_type",
            "document_id",
        )
        indexes = [
            models.Index(
                fields=["collection", "document_type"],
                name="document_collection_type_idx",
            ),
            models.Index(
                fields=["collection", "scielo_issn"],
                name="document_collection_issn_idx",
            ),
            models.Index(
                fields=["collection", "pid_v2"],
                name="document_collection_pidv2_idx",
            ),
            models.Index(
                fields=["collection", "pid_generic"],
                name="doc_coll_pidgen_idx",
            ),
        ]
