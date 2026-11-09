# Sparse daily maps omit days with no usage, but the map itself must exist.
CONFIRMED_DAYS_SUM_SCRIPT = """
String month = doc['month'].value.toString().substring(0,7);
if (params.complete.contains(month)) return doc[params.metric].value;

def daily = params._source.daily_metrics;
if (daily == null) throw new IllegalStateException('Missing daily_metrics');

long total = 0;
for (def day : params.days[month]) {
    def values = daily[day];
    if (values != null) total += values[params.metric];
}

return total;
"""
