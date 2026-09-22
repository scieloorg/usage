from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

app_name = "counter_api"

urlpatterns = [
    path(
        "schema/",
        SpectacularAPIView.as_view(urlconf="counter_api.schema_urls"),
        name="schema",
    ),
    path(
        "",
        SpectacularSwaggerView.as_view(url_name="counter_api:schema"),
        name="docs",
    ),
    path("", include("counter_api.api_urls")),
    path("extensions/", include("counter_api.extensions.urls")),
]
