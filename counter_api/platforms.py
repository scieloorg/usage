from collection.models import Collection
from counter_api.constants import HOST_TYPES
from counter_api.exceptions import insufficient_information


def get_platform(value):
    if not value:
        raise insufficient_information("platform is required")

    platform = Collection.objects.filter(acron3=value, is_active=True).first()
    if not platform or platform.collection_type not in HOST_TYPES:
        raise insufficient_information("platform is not recognized")
    return platform


def list_platforms():
    platforms = Collection.objects.filter(
        collection_type__in=HOST_TYPES,
        is_active=True,
    ).order_by("main_name")

    return [
        {
            "Platform_Parameter": platform.acron3,
            "Platform_Name": platform.main_name or platform.acron3,
            "Platform_Description": platform.domain or "",
        }
        for platform in platforms
    ]
