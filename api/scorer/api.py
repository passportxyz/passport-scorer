"""
The scorer API module
"""
from ceramic_cache.api import router as ceramic_cache_router
from django_ratelimit.exceptions import Ratelimited
from ninja import NinjaAPI
from registry.api.v1 import analytics_router
from registry.api.v1 import router as registry_router_v1
from registry.api.v2 import router as registry_router_v2

registry_api_v1 = NinjaAPI(
    urls_namespace="registry", title="Scorer API", version="1.0.0"
)
registry_api_v2 = NinjaAPI(
    urls_namespace="registry_v2", title="Scorer API", version="2.0.0"
)


@registry_api_v1.exception_handler(Ratelimited)
def service_unavailable(request, _):
    return registry_api_v1.create_response(
        request,
        {"detail": "You have been rate limited!"},
        status=429,
    )


registry_api_v1.add_router(
    "/registry/", registry_router_v1, tags=["Score your passport"]
)

registry_api_v2.add_router("", registry_router_v2, tags=["Score your passport"])

ceramic_cache_api = NinjaAPI(urls_namespace="ceramic-cache", docs_url=None)
ceramic_cache_api.add_router("", ceramic_cache_router)

analytics_api = NinjaAPI(urls_namespace="analytics", title="Data Analytics API")
analytics_api.add_router("", analytics_router)
