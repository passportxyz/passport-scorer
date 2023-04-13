import logging

from registry.tasks import save_api_key_analytics

log = logging.getLogger(__name__)


class ApiKeyRequestCounterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            path = request.path

            if path.startswith("/registry/"):

                # Extract the API key from the request header
                api_key_value = request.META.get("HTTP_X_API_KEY")

                if api_key_value:
                    # Using a task here to avoid blocking the request
                    save_api_key_analytics.delay(api_key_value, path)

        except Exception as e:
            log.error(
                "Exception while saving api key analytics. exception='%s'",
                e,
            )
            pass

        return response
