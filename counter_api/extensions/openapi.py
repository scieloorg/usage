from rest_framework import serializers


class RankingItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    count = serializers.IntegerField()


class RankingGroupSerializer(serializers.Serializer):
    dimensions = serializers.DictField()
    items = RankingItemSerializer(many=True)


class CoverageMonthSerializer(serializers.Serializer):
    month = serializers.CharField()
    status = serializers.ChoiceField(
        choices=["complete", "partial", "unavailable", "unknown"]
    )
    confirmed_days = serializers.ListField(child=serializers.IntegerField())
    missing_days = serializers.ListField(
        child=serializers.IntegerField(), allow_null=True
    )


class CoverageSerializer(serializers.Serializer):
    policy = serializers.CharField()
    status = serializers.ChoiceField(choices=["complete", "partial"])
    basis = serializers.ChoiceField(
        choices=["confirmed_days", "available_annual_totals"]
    )
    included_months = serializers.ListField(
        child=serializers.CharField(),
        allow_null=True,
        help_text="Null for annual totals: coverage is informative, not a day filter.",
    )
    months = CoverageMonthSerializer(many=True)


class CoverageResponseSerializer(serializers.Serializer):
    coverage = CoverageSerializer(required=False)
    warnings = serializers.ListField(child=serializers.CharField(), required=False)


class RankingSerializer(CoverageResponseSerializer):
    platform = serializers.CharField()
    begin_date = serializers.DateField()
    end_date = serializers.DateField()
    parent_type = serializers.CharField()
    parent_id = serializers.CharField()
    entity_type = serializers.CharField()
    metric_type = serializers.CharField()
    groups = RankingGroupSerializer(many=True)


class DistributionBucketSerializer(serializers.Serializer):
    value = serializers.CharField()
    dimensions = serializers.DictField()
    count = serializers.IntegerField()


class DistributionSerializer(CoverageResponseSerializer):
    platform = serializers.CharField()
    begin_date = serializers.DateField()
    end_date = serializers.DateField()
    entity_type = serializers.CharField()
    entity_id = serializers.CharField()
    dimension = serializers.CharField()
    dimensions = serializers.ListField(child=serializers.CharField())
    metric_type = serializers.CharField()
    total = serializers.IntegerField()
    buckets = DistributionBucketSerializer(many=True)


class CapabilitiesSerializer(serializers.Serializer):
    platform = serializers.CharField()
    ranking_relations = serializers.ListField(child=serializers.DictField())
    ranking_metrics = serializers.ListField(child=serializers.CharField())
    ranking_dimensions = serializers.ListField(child=serializers.CharField())
    download_formats = serializers.ListField(child=serializers.CharField())
    distribution_dimensions = serializers.ListField(child=serializers.CharField())
    country_language_granularity = serializers.CharField()
    other_granularity = serializers.CharField()
    first_month_available = serializers.CharField(allow_null=True)
    last_month_available = serializers.CharField(allow_null=True)
