from django.conf import settings
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from counter_api.exceptions import CounterAPIError
from counter_api.models import APIKey
from counter_api.negotiation import CounterContentNegotiation
from counter_api.rate_limit import RateLimitExceeded


class CounterAPIView(APIView):
    """Read-only COUNTER policy, independent of global JWT/admin access rules."""

    access_exempt = False

    authentication_classes = []
    permission_classes = []
    renderer_classes = [JSONRenderer]
    content_negotiation_class = CounterContentNegotiation
    http_method_names = ["get"]
    throttle_classes = []

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Preserve 405 for unsupported methods, even during Redis outages.
        if request.method != "GET" or self.access_exempt:
            return
        supplied = "api_key" in request.query_params
        key = None
        if supplied:
            values = request.query_params.getlist("api_key")
            if len(values) == 1:
                key = APIKey.authenticate(values[0])
        if (supplied and key is None) or (
            not supplied and settings.COUNTER_API_ACCESS_MODE == "key_required"
        ):
            raise CounterAPIError(2020, "APIKey Invalid", 401)

    def handle_exception(self, exc):
        if isinstance(exc, CounterAPIError):
            headers = {}
            if isinstance(exc, RateLimitExceeded):
                headers["Retry-After"] = str(exc.retry_after)
            return Response(exc.as_dict(), status=exc.status_code, headers=headers)
        return super().handle_exception(exc)
