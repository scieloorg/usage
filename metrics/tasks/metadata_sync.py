from config import celery_app
from metrics.services.metadata_sync import sync_metadata


@celery_app.task(
    bind=True,
    name="[Metadata] Sync OpenSearch metadata",
    queue="load",
    timelimit=-1,
)
def task_sync_opensearch_metadata(self, entity=None, batch_size=1000):
    return sync_metadata(entity=entity, batch_size=batch_size)
