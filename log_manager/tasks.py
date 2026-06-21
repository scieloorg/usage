import logging

from celery import chord

from config import celery_app
from config.collections import get_collection_parse_queue
from core.utils.request_utils import _get_user
from log_manager.services import catalog, validation
from metrics.tasks.log_parsing import task_enqueue_log_parsing_jobs


@celery_app.task(bind=True, name="[Log Pipeline] 1. Search Logs (Manual)", queue="load")
def task_search_log_files(
    self,
    collections=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    user_id=None,
    username=None,
    trigger_validation=False,
):
    """
    Search for log files in configured collection directories.

    When trigger_validation=True, this starts the full Search -> Validate -> Parse
    chain. Parse callbacks are routed by collection size.
    """
    _get_user(self.request, username=username, user_id=user_id)

    catalog.catalog_log_files_from_configured_directories(
        collections=collections,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
    )

    if trigger_validation:
        task_validate_log_files.apply_async(
            kwargs={
                "collections": collections,
                "from_date": from_date,
                "until_date": until_date,
                "days_to_go_back": days_to_go_back,
                "user_id": user_id,
                "username": username,
                "trigger_parse": True,
            }
        )


@celery_app.task(
    bind=True,
    name="[Log Pipeline] 2. Validate Logs (Manual)",
    timelimit=-1,
    queue="load",
)
def task_validate_log_files(
    self,
    collections=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    user_id=None,
    username=None,
    ignore_date=False,
    trigger_parse=False,
    revalidate=False,
    status_list=None,
):
    """
    Validate cataloged log files.

    When trigger_parse=True, one parse orchestration task is enqueued per
    collection and routed to the proper parse_<size> queue.
    """
    log_hashes_by_collection = validation.get_validation_candidate_hashes_by_collection(
        collections=collections,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        ignore_date=ignore_date,
        revalidate=revalidate,
        status_list=status_list,
    )
    if log_hashes_by_collection is None:
        return

    tasks_by_collection = _build_validation_tasks(
        log_hashes_by_collection=log_hashes_by_collection,
        user_id=user_id,
        username=username,
    )

    if trigger_parse:
        _enqueue_parse_after_validation(
            tasks_by_collection=tasks_by_collection,
            from_date=from_date,
            until_date=until_date,
            days_to_go_back=days_to_go_back,
            user_id=user_id,
            username=username,
        )
        return

    for collection_tasks in tasks_by_collection.values():
        for validation_task in collection_tasks:
            validation_task.apply_async()


@celery_app.task(
    bind=True,
    name="[Log Pipeline] Validate Single Log File (Auto)",
    timelimit=-1,
    queue="load",
)
def task_validate_log_file(self, log_file_hash, user_id=None, username=None):
    """Validate a single LogFile and update its status."""
    _get_user(self.request, username=username, user_id=user_id)
    validation.validate_log_file_and_update_status(log_file_hash)


@celery_app.task(bind=True, name="[Log Pipeline] Daily Routine (Auto)", queue="load")
def task_daily_log_ingestion_pipeline(self):
    """
    Start the daily Search -> Validate -> Parse chain with default parameters.
    """
    logging.info("Starting Daily Log Ingestion Pipeline")
    task_search_log_files.apply_async(kwargs={"trigger_validation": True})


def _build_validation_tasks(log_hashes_by_collection, user_id, username):
    return {
        collection_code: [
            task_validate_log_file.s(log_file_hash, user_id, username)
            for log_file_hash in log_hashes
        ]
        for collection_code, log_hashes in log_hashes_by_collection.items()
    }


def _enqueue_parse_after_validation(
    tasks_by_collection, from_date, until_date, days_to_go_back, user_id, username
):
    for collection_code, validation_tasks in tasks_by_collection.items():
        if validation_tasks:
            chord(validation_tasks)(
                _build_parse_signature(
                    collection_code,
                    from_date,
                    until_date,
                    days_to_go_back,
                    user_id,
                    username,
                )
            )
        else:
            task_enqueue_log_parsing_jobs.apply_async(
                **_build_parse_apply_kwargs(
                    collection_code,
                    from_date,
                    until_date,
                    days_to_go_back,
                    user_id,
                    username,
                )
            )


def _build_parse_signature(
    collection_code, from_date, until_date, days_to_go_back, user_id, username
):
    apply_kwargs = _build_parse_apply_kwargs(
        collection_code,
        from_date,
        until_date,
        days_to_go_back,
        user_id,
        username,
    )
    parse_callback = task_enqueue_log_parsing_jobs.si(**apply_kwargs["kwargs"])
    if apply_kwargs.get("queue"):
        parse_callback.set(queue=apply_kwargs["queue"])
    return parse_callback


def _build_parse_apply_kwargs(
    collection_code, from_date, until_date, days_to_go_back, user_id, username
):
    collections = [collection_code]
    parse_queue = get_collection_parse_queue(collection_code)
    apply_kwargs = {
        "kwargs": {
            "collections": collections,
            "from_date": from_date,
            "until_date": until_date,
            "days_to_go_back": days_to_go_back,
            "queue_name": parse_queue,
            "user_id": user_id,
            "username": username,
        },
        "queue": parse_queue,
    }
    return apply_kwargs
