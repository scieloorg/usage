import pytest

from collection.models import Collection


@pytest.mark.django_db
def test_articlemeta_load_preserves_configured_opac_url():
    collection = Collection.objects.create(
        acron3="dom",
        opac_url="https://scielo.do/api/v1/counter_dict",
    )

    Collection.load(
        user=None,
        collections_data=[
            {
                "original_name": "República Dominicana",
                "acron2": "do",
                "acron": "dom",
                "code": "dom",
                "domain": "scielo.do",
                "name": {},
                "status": "development",
                "has_analytics": True,
                "type": "journals",
                "is_active": True,
            }
        ],
    )

    collection.refresh_from_db()
    assert collection.opac_url == "https://scielo.do/api/v1/counter_dict"
