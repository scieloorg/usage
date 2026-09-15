from datetime import date

from metrics.opensearch.painless import (
    ANNUAL_MASK_BITS,
    ANNUAL_MASK_BUCKETS,
    METRIC_FIELDS,
)

IDEMPOTENT_COUNTER_INCREMENT_SCRIPT = """
if (ctx._source.applied_migrations == null) {
  ctx._source.applied_migrations = [];
}
if (ctx._source.applied_migrations.contains(params.migration_id)) {
  ctx.op = 'none';
  return;
}
if (ctx._source.applied_days == null) {
  ctx._source.applied_days = [];
}
for (day in params.source_days) {
  if (ctx._source.applied_days.contains(day)) {
    throw new IllegalStateException('Historical migration overlaps applied day ' + day);
  }
}
for (entry in params.document.entrySet()) {
  if (!params.metric_fields.contains(entry.getKey())
      && !'applied_days'.equals(entry.getKey())
      && !'applied_migrations'.equals(entry.getKey())
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
if (ctx._source.daily_metrics == null) {
  ctx._source.daily_metrics = new HashMap();
}
for (dayEntry in params.document.daily_metrics.entrySet()) {
  ctx._source.daily_metrics[dayEntry.getKey()] = dayEntry.getValue();
}
ctx._source.applied_days.addAll(params.source_days);
ctx._source.applied_migrations.add(params.migration_id);
"""

IDEMPOTENT_ANALYTICS_INCREMENT_SCRIPT = """
if (ctx._source.applied_migrations == null) {
  ctx._source.applied_migrations = [];
}
if (ctx._source.applied_migrations.contains(params.migration_id)) {
  ctx.op = 'none';
  return;
}
if (ctx._source.applied_day_masks == null) {
  ctx._source.applied_day_masks = params.empty_day_masks;
}
for (int index = 0; index < params.day_masks.size(); index++) {
  if ((ctx._source.applied_day_masks[index] & params.day_masks[index]) != 0) {
    throw new IllegalStateException('Historical migration overlaps an applied analytics day');
  }
}
for (entry in params.document.entrySet()) {
  if (!params.metric_fields.contains(entry.getKey())
      && !'applied_day_masks'.equals(entry.getKey())
      && !'applied_migrations'.equals(entry.getKey())) {
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
for (int index = 0; index < params.day_masks.size(); index++) {
  ctx._source.applied_day_masks[index] |= params.day_masks[index];
}
ctx._source.applied_migrations.add(params.migration_id);
"""


def build_counter_increment_action(
    index_name,
    doc_id,
    document,
    migration_id,
    source_days,
):
    month = document["month"]
    document_source_days = [
        "%s-%s" % (month, day) for day in sorted(document["daily_metrics"])
    ]
    if set(document_source_days) - set(source_days):
        raise ValueError(
            "Counter document contains days outside the migration source period."
        )

    return {
        "_op_type": "update",
        "_index": index_name,
        "_id": doc_id,
        "retry_on_conflict": 5,
        "scripted_upsert": True,
        "script": {
            "lang": "painless",
            "source": IDEMPOTENT_COUNTER_INCREMENT_SCRIPT,
            "params": {
                "document": document,
                "migration_id": migration_id,
                "source_days": document_source_days,
                "metric_fields": list(METRIC_FIELDS),
            },
        },
        "upsert": {
            "applied_days": [],
            "applied_migrations": [],
        },
    }


def build_analytics_increment_action(
    index_name,
    doc_id,
    document,
    migration_id,
    source_days,
):
    day_masks = [0] * ANNUAL_MASK_BUCKETS
    for access_day in source_days:
        access_date = date.fromisoformat(access_day)
        day_offset = access_date.timetuple().tm_yday - 1
        day_masks[day_offset // ANNUAL_MASK_BITS] |= 1 << (
            day_offset % ANNUAL_MASK_BITS
        )

    return {
        "_op_type": "update",
        "_index": index_name,
        "_id": doc_id,
        "retry_on_conflict": 5,
        "scripted_upsert": True,
        "script": {
            "lang": "painless",
            "source": IDEMPOTENT_ANALYTICS_INCREMENT_SCRIPT,
            "params": {
                "document": document,
                "migration_id": migration_id,
                "day_masks": day_masks,
                "empty_day_masks": [0] * ANNUAL_MASK_BUCKETS,
                "metric_fields": list(METRIC_FIELDS),
            },
        },
        "upsert": {
            "applied_day_masks": [0] * ANNUAL_MASK_BUCKETS,
            "applied_migrations": [],
        },
    }
