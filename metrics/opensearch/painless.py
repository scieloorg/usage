METRIC_FIELDS = (
    "total_requests",
    "total_investigations",
    "unique_requests",
    "unique_investigations",
)

IDEMPOTENT_JOB_INCREMENT_SCRIPT = """
if (ctx._source.applied_jobs == null) {
  ctx._source.applied_jobs = [];
}
if (ctx._source.applied_jobs.contains(params.job_id)) {
  ctx.op = 'none';
  return;
}
for (entry in params.document.entrySet()) {
  if (!params.metric_fields.contains(entry.getKey())
      && !'applied_jobs'.equals(entry.getKey())
      && !'daily_metrics'.equals(entry.getKey())) {
    if (!ctx._source.containsKey(entry.getKey()) || ctx._source[entry.getKey()] != entry.getValue()) {
      ctx._source[entry.getKey()] = entry.getValue();
    }
  }
}
for (field in params.metric_fields) {
  def currentValue = ctx._source.containsKey(field) ? ctx._source[field] : 0;
  def increment = params.document.containsKey(field) ? params.document[field] : 0;
  ctx._source[field] = currentValue + increment;
}
if (params.document.containsKey('daily_metrics')) {
  if (!ctx._source.containsKey('daily_metrics') || ctx._source.daily_metrics == null) {
    ctx._source.daily_metrics = new HashMap();
  }
  for (dayEntry in params.document.daily_metrics.entrySet()) {
    def day = dayEntry.getKey();
    def dayMetrics = dayEntry.getValue();
    if (!ctx._source.daily_metrics.containsKey(day) || ctx._source.daily_metrics[day] == null) {
      ctx._source.daily_metrics[day] = new HashMap();
    }
    for (metric in params.metric_fields) {
      def currentValue = ctx._source.daily_metrics[day].containsKey(metric)
        ? ctx._source.daily_metrics[day][metric] : 0;
      def increment = dayMetrics.containsKey(metric) ? dayMetrics[metric] : 0;
      ctx._source.daily_metrics[day][metric] = currentValue + increment;
    }
  }
}
ctx._source.applied_jobs.add(params.job_id);
"""


def build_idempotent_job_increment_action(index_name, doc_id, document, job_id):
    return {
        "_op_type": "update",
        "_index": index_name,
        "_id": doc_id,
        "retry_on_conflict": 5,
        "scripted_upsert": True,
        "script": {
            "lang": "painless",
            "source": IDEMPOTENT_JOB_INCREMENT_SCRIPT,
            "params": {
                "document": document,
                "job_id": job_id,
                "metric_fields": list(METRIC_FIELDS),
            },
        },
        "upsert": {
            "applied_jobs": [],
        },
    }


def merge_metric_document(existing, current, operation="add"):
    if existing is None:
        if operation == "subtract":
            return None
        return current

    merged = dict(existing)
    merged.update(
        {
            key: value
            for key, value in current.items()
            if key not in METRIC_FIELDS and key != "daily_metrics"
        }
    )

    signal = -1 if operation == "subtract" else 1
    for field in METRIC_FIELDS:
        merged[field] = existing.get(field, 0) + signal * current.get(field, 0)

    if "daily_metrics" in current:
        merged_daily = dict(existing.get("daily_metrics") or {})
        for day, metrics in current["daily_metrics"].items():
            day_merged = dict(merged_daily.get(day) or {})
            for field in METRIC_FIELDS:
                day_merged[field] = day_merged.get(field, 0) + signal * metrics.get(
                    field, 0
                )
            merged_daily[day] = day_merged
        merged["daily_metrics"] = merged_daily

    if all(merged.get(field, 0) <= 0 for field in METRIC_FIELDS):
        return None

    return merged
