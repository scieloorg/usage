from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

app_name = "pid_provider"

if settings.DEBUG:
    router = DefaultRouter()
else:
    router = SimpleRouter()

urlpatterns = router.urls
