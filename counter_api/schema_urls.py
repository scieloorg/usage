from django.urls import include, path

urlpatterns = [
    path("r51/", include("counter_api.api_urls")),
    path("r51/extensions/", include("counter_api.extensions.urls")),
]
