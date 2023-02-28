"""
The scorer API module
"""
from ceramic_cache.api import router as ceramic_cache_router
from django_ratelimit.exceptions import Ratelimited
from ninja import NinjaAPI
from registry.api import analytics_router
from registry.api import router as registry_router

registry_api = NinjaAPI(urls_namespace="registry", title="Scorer API")


@registry_api.exception_handler(Ratelimited)
def service_unavailable(request, _exc):
    # pylint: disable=unused-argument,invalid-name
    return registry_api.create_response(
        request,
        {"detail": "You have been rate limited!"},
        status=429,
    )


registry_api.add_router("/registry/", registry_router, tags=["Score your passport"])

ceramic_cache_api = NinjaAPI(urls_namespace="ceramic-cache", docs_url=None)
ceramic_cache_api.add_router("", ceramic_cache_router)

analytics_api = NinjaAPI(urls_namespace="analytics", title="Data Analytics API")
analytics_api.add_router("", analytics_router)
