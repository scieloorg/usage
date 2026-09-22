from datetime import date

ANNUAL_MASK_BITS = 63
DAYS_PER_LEAP_YEAR = 366
ANNUAL_MASK_BUCKETS = (DAYS_PER_LEAP_YEAR + ANNUAL_MASK_BITS - 1) // ANNUAL_MASK_BITS
METRIC_FIELDS = (
    "total_requests",
    "total_investigations",
    "unique_requests",
    "unique_investigations",
)

IDEMPOTENT_DAY_INCREMENT_SCRIPT = """
if (ctx._source.applied_days == null) {
  ctx._source.applied_days = [];
}
if (ctx._source.applied_days.contains(params.access_day)) {
  ctx.op = 'none';
  return;
}
for (entry in params.document.entrySet()) {
  if (!params.metric_fields.contains(entry.getKey())
      && !'applied_days'.equals(entry.getKey())
      && !'daily_metrics'.equals(entry.getKey())) {
    if ('publication_year'.equals(entry.getKey())
        && ctx._source.containsKey(entry.getKey())
        && ctx._source[entry.getKey()] != null
        && ctx._source[entry.getKey()] != 1
        && entry.getValue() == 1) {
      continue;
    }
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
ctx._source.applied_days.add(params.access_day);
"""

IDEMPOTENT_ANNUAL_DAY_INCREMENT_SCRIPT = """
if (ctx._source.applied_day_masks == null) {
  ctx._source.applied_day_masks = params.empty_day_masks;
}
def currentMask = ctx._source.applied_day_masks[params.mask_index];
if ((currentMask & params.day_mask) != 0) {
  ctx.op = 'none';
  return;
}
for (entry in params.document.entrySet()) {
  if (!params.metric_fields.contains(entry.getKey())
      && !'applied_day_masks'.equals(entry.getKey())) {
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
ctx._source.applied_day_masks[params.mask_index] = currentMask | params.day_mask;
"""


def build_idempotent_day_increment_action(
    index_name,
    doc_id,
    document,
    access_day,
):
    return {
        "_op_type": "update",
        "_index": index_name,
        "_id": doc_id,
        "retry_on_conflict": 5,
        "scripted_upsert": True,
        "script": {
            "lang": "painless",
            "source": IDEMPOTENT_DAY_INCREMENT_SCRIPT,
            "params": {
                "document": document,
                "access_day": access_day,
                "metric_fields": list(METRIC_FIELDS),
            },
        },
        "upsert": {
            "applied_days": [],
        },
    }


def build_idempotent_annual_day_increment_action(
    index_name,
    doc_id,
    document,
    access_day,
):
    access_date = date.fromisoformat(access_day)
    day_offset = access_date.timetuple().tm_yday - 1
    return {
        "_op_type": "update",
        "_index": index_name,
        "_id": doc_id,
        "retry_on_conflict": 5,
        "scripted_upsert": True,
        "script": {
            "lang": "painless",
            "source": IDEMPOTENT_ANNUAL_DAY_INCREMENT_SCRIPT,
            "params": {
                "document": document,
                "mask_index": day_offset // ANNUAL_MASK_BITS,
                "day_mask": 1 << (day_offset % ANNUAL_MASK_BITS),
                "empty_day_masks": [0] * ANNUAL_MASK_BUCKETS,
                "metric_fields": list(METRIC_FIELDS),
            },
        },
        "upsert": {
            "applied_day_masks": [0] * ANNUAL_MASK_BUCKETS,
        },
    }


def merge_metric_document(existing, current, operation="add"):
    if existing is None:
        if operation == "subtract":
            return None
        return current

    merged = dict(existing)
    metadata = {
        key: value
        for key, value in current.items()
        if key not in METRIC_FIELDS and key != "daily_metrics"
    }
    if existing.get("publication_year") not in {None, 1}:
        if metadata.get("publication_year") == 1:
            metadata.pop("publication_year")
    merged.update(metadata)

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
