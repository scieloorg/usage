from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from counter_api.exceptions import CounterAPIError
from counter_api.models import APIKey
from counter_api.negotiation import CounterContentNegotiation


class CounterAPIView(APIView):
    authentication_classes = []
    permission_classes = []
    renderer_classes = [JSONRenderer]
    content_negotiation_class = CounterContentNegotiation
    http_method_names = ["get"]


def get_authentication_error(request):
    key = APIKey.authenticate(request.query_params.get("api_key"))
    if key:
        return None

    error = CounterAPIError(2020, "APIKey Invalid", 401)

    return Response(error.as_dict(), status=error.status_code)
