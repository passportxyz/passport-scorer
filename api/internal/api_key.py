from django.conf import settings
from ninja.security import APIKeyHeader


class InternalApiKey(APIKeyHeader):
    param_name = "AUTHORIZATION"

    def authenticate(self, request, key):
        if key == settings.CGRANTS_API_TOKEN:
            return key


internal_api_key = InternalApiKey()
