import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from document.models import Document
from metrics.models import MetadataSyncOutbox, MetadataSyncState
from metrics.opensearch.client import OpenSearchUsageClient
from metrics.opensearch.mappings import get_index_mappings
from metrics.opensearch.names import generate_metadata_alias
from metrics.services.metadata_documents import (
    build_document_document,
    build_source_document,
)
from source.models import Source

DEFAULT_BATCH_SIZE = 1000
LEASE_MINUTES = 30


def sync_metadata(entity=None, batch_size=DEFAULT_BATCH_SIZE):
    entities = (
        [entity]
        if entity
        else [
            MetadataSyncState.ENTITY_SOURCE,
            MetadataSyncState.ENTITY_DOCUMENT,
        ]
    )
    result = {}
    client = OpenSearchUsageClient()
    if not client.ping():
        raise RuntimeError("OpenSearch client is not available.")

    for current_entity in entities:
        result[current_entity] = _sync_entity(client, current_entity, batch_size)
    return result


def _sync_entity(client, entity, batch_size):
    model, serializer, related = _entity_config(entity)
    state = _acquire_lease(entity)
    alias = generate_metadata_alias(f"{entity}s")
    client.create_alias_if_not_exists(alias, get_index_mappings(f"{entity}s"))
    exported = 0

    try:
        while True:
            batch = list(_cursor_queryset(model, state, related)[:batch_size])
            if not batch:
                break
            exported += client.index_document_items(
                alias,
                (serializer(item) for item in batch),
            )
            last = batch[-1]
            state.cursor_updated = last.updated
            state.cursor_pk = last.pk
            _heartbeat(state)

        exported += _flush_outbox(client, entity, alias, batch_size)
        state.completed_at = timezone.now()
        return exported
    finally:
        state.lease_until = None
        state.heartbeat_at = timezone.now()
        state.save(
            update_fields=[
                "cursor_updated",
                "cursor_pk",
                "lease_until",
                "heartbeat_at",
                "completed_at",
            ]
        )
        logging.info("Metadata sync completed for %s: %s documents.", entity, exported)


def _entity_config(entity):
    if entity == MetadataSyncState.ENTITY_SOURCE:
        return Source, build_source_document, ("collection",)
    if entity == MetadataSyncState.ENTITY_DOCUMENT:
        return (
            Document,
            build_document_document,
            (
                "collection",
                "source",
                "parent_document",
            ),
        )
    raise ValueError(f"Unsupported metadata entity: {entity}.")


def _cursor_queryset(model, state, related):
    queryset = model.objects.select_related(*related).order_by("updated", "pk")
    if state.cursor_updated is None:
        return queryset
    return queryset.filter(
        Q(updated__gt=state.cursor_updated)
        | Q(updated=state.cursor_updated, pk__gt=state.cursor_pk)
    )


def _acquire_lease(entity):
    now = timezone.now()
    with transaction.atomic():
        state, _created = MetadataSyncState.objects.select_for_update().get_or_create(
            entity=entity
        )
        if state.lease_until and state.lease_until > now:
            raise RuntimeError(f"Metadata sync already running for {entity}.")
        state.lease_until = now + timedelta(minutes=LEASE_MINUTES)
        state.heartbeat_at = now
        state.save(update_fields=["lease_until", "heartbeat_at"])
    return state


def _heartbeat(state):
    now = timezone.now()
    state.heartbeat_at = now
    state.lease_until = now + timedelta(minutes=LEASE_MINUTES)
    state.save(
        update_fields=[
            "cursor_updated",
            "cursor_pk",
            "heartbeat_at",
            "lease_until",
        ]
    )


def _flush_outbox(client, entity, alias, batch_size):
    exported = 0
    while True:
        entries = list(
            MetadataSyncOutbox.objects.filter(entity=entity).order_by("pk")[:batch_size]
        )
        if not entries:
            return exported

        exported += client.index_document_items(
            alias,
            ((entry.object_key, entry.payload) for entry in entries),
        )
        MetadataSyncOutbox.objects.filter(
            pk__in=[entry.pk for entry in entries]
        ).delete()
