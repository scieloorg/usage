from config import celery_app
from reports.services import emails, log_report


@celery_app.task(bind=True, name="[Reports] Populate All Reports")
def task_populate_all_reports(self, year=None, collection_acron=None):
    return log_report.populate_log_report_tables(
        year=year,
        collection_acron=collection_acron,
    )


@celery_app.task(
    bind=True,
    name="[Reports] Generate Log Report Summary (Manual)",
    queue="load",
)
def task_log_files_count_status_report(
    self,
    collections=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    user_id=None,
    username=None,
):
    return emails.send_log_report_summary_emails(
        collections=collections,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
    )
