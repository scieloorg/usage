from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from document.models import Document
from metrics.models import MetadataSyncOutbox, MetadataSyncState
from metrics.services.metadata_documents import (
    build_document_document,
    build_document_tombstone,
    build_source_document,
    build_source_tombstone,
)
from source.models import Source


def _put(entity, item):
    object_key, payload = item
    MetadataSyncOutbox.objects.update_or_create(
        entity=entity,
        object_key=object_key,
        defaults={"payload": payload},
    )


@receiver(post_save, sender=Source)
def source_saved(sender, instance, **kwargs):
    _put(MetadataSyncState.ENTITY_SOURCE, build_source_document(instance))


@receiver(pre_delete, sender=Source)
def source_deleted(sender, instance, **kwargs):
    _put(MetadataSyncState.ENTITY_SOURCE, build_source_tombstone(instance))


@receiver(post_save, sender=Document)
def document_saved(sender, instance, **kwargs):
    _put(MetadataSyncState.ENTITY_DOCUMENT, build_document_document(instance))


@receiver(pre_delete, sender=Document)
def document_deleted(sender, instance, **kwargs):
    _put(MetadataSyncState.ENTITY_DOCUMENT, build_document_tombstone(instance))
