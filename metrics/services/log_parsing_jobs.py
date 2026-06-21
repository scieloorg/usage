from collection.models import Collection
from config.collections import get_collection_parse_queue
from core.utils.date_utils import get_date_obj, get_date_range_str
from log_manager import choices
from log_manager.models import LogFile
from metrics.models import DailyMetricJob
from metrics.services.jobs import create_or_update_daily_metric_job

AUTO_REEXECUTE_POLL_INTERVAL_SECONDS = 30


def enqueue_log_parsing_jobs(
    daily_metric_export_task,
    wait_log_parsing_wave_task,
    collections=None,
    include_logs_with_error=True,
    batch_size=5000,
    max_log_files=None,
    auto_reexecute=False,
    replace=False,
    track_errors=False,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    queue_name=None,
    user_id=None,
    username=None,
    skip_log_hashes=None,
    robots_source=None,
):
    from_date, until_date = get_date_range_str(from_date, until_date, days_to_go_back)
    from_date_obj = get_date_obj(from_date)
    until_date_obj = get_date_obj(until_date)
    enqueued_logs = 0
    enqueued_jobs = 0
    reached_max_log_files = False
    enqueued_wave_job_ids = []
    claimed_status_filters = list(_build_log_status_filters(include_logs_with_error))
    skip_log_hashes = set(skip_log_hashes or [])

    for collection in collections or Collection.acron3_list():
        collection_obj = Collection.objects.filter(acron3=collection).first()
        if collection_obj is None:
            continue

        result = _enqueue_collection_daily_jobs(
            daily_metric_export_task=daily_metric_export_task,
            collection=collection_obj,
            from_date_obj=from_date_obj,
            until_date_obj=until_date_obj,
            status_filters=claimed_status_filters,
            skip_log_hashes=skip_log_hashes,
            enqueued_logs=enqueued_logs,
            max_log_files=max_log_files,
            track_errors=track_errors,
            user_id=user_id,
            username=username,
            robots_source=robots_source,
            queue_name=queue_name,
        )

        enqueued_logs += result["enqueued_logs"]
        enqueued_jobs += result["enqueued_jobs"]
        enqueued_wave_job_ids.extend(result["enqueued_wave_job_ids"])
        reached_max_log_files = result["reached_max_log_files"]
        if result["reached_max_log_files"]:
            break

    auto_reexecution_enqueued = _schedule_log_parsing_reexecution(
        wait_log_parsing_wave_task=wait_log_parsing_wave_task,
        should_reexecute=(
            auto_reexecute and reached_max_log_files and bool(enqueued_wave_job_ids)
        ),
        wave_job_ids=enqueued_wave_job_ids,
        collections=collections,
        include_logs_with_error=include_logs_with_error,
        batch_size=batch_size,
        max_log_files=max_log_files,
        auto_reexecute=auto_reexecute,
        replace=replace,
        track_errors=track_errors,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        skip_log_hashes=sorted(skip_log_hashes),
        robots_source=robots_source,
    )

    return {
        "enqueued_logs": enqueued_logs,
        "enqueued_jobs": enqueued_jobs,
        "reached_max_log_files": reached_max_log_files,
        "auto_reexecution_enqueued": auto_reexecution_enqueued,
    }


def wait_log_parsing_wave(
    log_parsing_task,
    wait_log_parsing_wave_task,
    wave_job_ids=None,
    collections=None,
    include_logs_with_error=True,
    batch_size=5000,
    max_log_files=None,
    auto_reexecute=False,
    replace=False,
    track_errors=False,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    queue_name=None,
    user_id=None,
    username=None,
    skip_log_hashes=None,
    poll_interval_seconds=AUTO_REEXECUTE_POLL_INTERVAL_SECONDS,
    robots_source=None,
    wave_log_hashes=None,
):
    wave_job_ids = wave_job_ids or wave_log_hashes or []
    if DailyMetricJob.objects.filter(
        pk__in=wave_job_ids,
        status__in=[DailyMetricJob.STATUS_PENDING, DailyMetricJob.STATUS_EXPORTING],
    ).exists():
        kwargs = _build_log_parsing_reexecution_kwargs(
            wave_job_ids=wave_job_ids,
            collections=collections,
            include_logs_with_error=include_logs_with_error,
            batch_size=batch_size,
            max_log_files=max_log_files,
            auto_reexecute=auto_reexecute,
            replace=replace,
            track_errors=track_errors,
            from_date=from_date,
            until_date=until_date,
            days_to_go_back=days_to_go_back,
            queue_name=queue_name,
            user_id=user_id,
            username=username,
            skip_log_hashes=skip_log_hashes,
            poll_interval_seconds=poll_interval_seconds,
            robots_source=robots_source,
        )
        apply_kwargs = {
            "kwargs": kwargs,
            "countdown": poll_interval_seconds,
        }
        if queue_name:
            apply_kwargs["queue"] = queue_name
        wait_log_parsing_wave_task.apply_async(**apply_kwargs)
        return {"wave_completed": False, "reexecution_enqueued": False}

    kwargs = _build_log_parsing_kwargs(
        collections=collections,
        include_logs_with_error=include_logs_with_error,
        batch_size=batch_size,
        max_log_files=max_log_files,
        auto_reexecute=auto_reexecute,
        replace=replace,
        track_errors=track_errors,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        skip_log_hashes=skip_log_hashes,
        robots_source=robots_source,
    )
    apply_kwargs = {"kwargs": kwargs}
    if queue_name:
        apply_kwargs["queue"] = queue_name
    log_parsing_task.apply_async(**apply_kwargs)
    return {"wave_completed": True, "reexecution_enqueued": True}


def _build_log_status_filters(include_logs_with_error):
    status_filters = [choices.LOG_FILE_STATUS_QUEUED]
    if include_logs_with_error:
        status_filters.append(choices.LOG_FILE_STATUS_ERROR)
    return tuple(status_filters)


def _enqueue_collection_daily_jobs(
    daily_metric_export_task,
    collection,
    from_date_obj,
    until_date_obj,
    status_filters,
    skip_log_hashes,
    enqueued_logs,
    max_log_files,
    track_errors,
    user_id,
    username,
    robots_source,
    queue_name,
):
    result = {
        "enqueued_logs": 0,
        "enqueued_jobs": 0,
        "enqueued_wave_job_ids": [],
        "reached_max_log_files": False,
    }

    access_dates = LogFile.distinct_access_dates_for_parsing(
        collection=collection,
        from_date=from_date_obj,
        until_date=until_date_obj,
        status_filters=status_filters,
        skip_hashes=skip_log_hashes,
    )

    for access_date in access_dates:
        log_files = LogFile.for_collection_date(
            collection=collection,
            access_date=access_date,
            status_filters=status_filters,
        )
        log_files = [
            log_file for log_file in log_files if log_file.hash not in skip_log_hashes
        ]

        reached_limit = False
        if max_log_files:
            remaining_log_slots = max_log_files - (
                enqueued_logs + result["enqueued_logs"]
            )
            if remaining_log_slots <= 0:
                result["reached_max_log_files"] = True
                break
            if len(log_files) > remaining_log_slots:
                log_files = log_files[:remaining_log_slots]
                reached_limit = True
        result["reached_max_log_files"] = reached_limit

        if not log_files:
            continue

        job = create_or_update_daily_metric_job(
            collection=collection,
            access_date=access_date,
            log_files=log_files,
        )
        if job.status == DailyMetricJob.STATUS_EXPORTED:
            if reached_limit:
                break
            continue

        daily_metric_export_task.apply_async(
            args=(job.pk, track_errors, user_id, username, robots_source),
            queue=queue_name or get_collection_parse_queue(collection.acron3),
        )
        result["enqueued_wave_job_ids"].append(job.pk)
        result["enqueued_jobs"] += 1
        result["enqueued_logs"] += len(log_files)
        if max_log_files and enqueued_logs + result["enqueued_logs"] >= max_log_files:
            result["reached_max_log_files"] = True

        if result["reached_max_log_files"]:
            break

    return result


def _schedule_log_parsing_reexecution(
    wait_log_parsing_wave_task,
    should_reexecute,
    wave_job_ids,
    collections,
    include_logs_with_error,
    batch_size,
    max_log_files,
    auto_reexecute,
    replace,
    track_errors,
    from_date,
    until_date,
    days_to_go_back,
    queue_name,
    user_id,
    username,
    skip_log_hashes,
    robots_source=None,
):
    if not should_reexecute:
        return False

    kwargs = _build_log_parsing_reexecution_kwargs(
        wave_job_ids=wave_job_ids,
        collections=collections,
        include_logs_with_error=include_logs_with_error,
        batch_size=batch_size,
        max_log_files=max_log_files,
        auto_reexecute=auto_reexecute,
        replace=replace,
        track_errors=track_errors,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        queue_name=queue_name,
        user_id=user_id,
        username=username,
        skip_log_hashes=skip_log_hashes,
        poll_interval_seconds=AUTO_REEXECUTE_POLL_INTERVAL_SECONDS,
        robots_source=robots_source,
    )

    apply_kwargs = {"kwargs": kwargs}
    if queue_name:
        apply_kwargs["queue"] = queue_name
    wait_log_parsing_wave_task.apply_async(**apply_kwargs)
    return True


def _build_log_parsing_reexecution_kwargs(
    wave_job_ids,
    collections,
    include_logs_with_error,
    batch_size,
    max_log_files,
    auto_reexecute,
    replace,
    track_errors,
    from_date,
    until_date,
    days_to_go_back,
    queue_name,
    user_id,
    username,
    skip_log_hashes,
    poll_interval_seconds,
    robots_source=None,
):
    kwargs = {
        "wave_job_ids": wave_job_ids,
        "collections": collections,
        "include_logs_with_error": include_logs_with_error,
        "batch_size": batch_size,
        "max_log_files": max_log_files,
        "auto_reexecute": auto_reexecute,
        "replace": replace,
        "track_errors": track_errors,
        "from_date": from_date,
        "until_date": until_date,
        "days_to_go_back": days_to_go_back,
        "queue_name": queue_name,
        "user_id": user_id,
        "username": username,
        "skip_log_hashes": skip_log_hashes,
        "poll_interval_seconds": poll_interval_seconds,
    }
    if robots_source is not None:
        kwargs["robots_source"] = robots_source
    return kwargs


def _build_log_parsing_kwargs(
    collections,
    include_logs_with_error,
    batch_size,
    max_log_files,
    auto_reexecute,
    replace,
    track_errors,
    from_date,
    until_date,
    days_to_go_back,
    queue_name,
    user_id,
    username,
    skip_log_hashes,
    robots_source=None,
):
    kwargs = {
        "collections": collections,
        "include_logs_with_error": include_logs_with_error,
        "batch_size": batch_size,
        "max_log_files": max_log_files,
        "auto_reexecute": auto_reexecute,
        "replace": replace,
        "track_errors": track_errors,
        "from_date": from_date,
        "until_date": until_date,
        "days_to_go_back": days_to_go_back,
        "queue_name": queue_name,
        "user_id": user_id,
        "username": username,
        "skip_log_hashes": skip_log_hashes,
    }
    if robots_source is not None:
        kwargs["robots_source"] = robots_source
    return kwargs
