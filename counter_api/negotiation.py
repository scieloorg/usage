from rest_framework.negotiation import BaseContentNegotiation


class CounterContentNegotiation(BaseContentNegotiation):
    def select_parser(self, request, parsers):
        return None

    def select_renderer(self, request, renderers, format_suffix=None):
        renderer = renderers[0]

        return renderer, renderer.media_type
