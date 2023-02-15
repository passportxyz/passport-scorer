"""
The scorer API module
"""
from ceramic_cache.api import router as ceramic_cache_router
from django.conf import settings
from ninja import NinjaAPI
from registry.api import analytics_router
from registry.api import router as registry_router

registry_api = NinjaAPI(urls_namespace="registry", title="Scorer API")
registry_api.add_router("/registry/", registry_router, tags=["Score your passport"])

ceramic_cache_api = NinjaAPI(urls_namespace="ceramic-cache", docs_url=None)
ceramic_cache_api.add_router("", ceramic_cache_router)

analytics_api = NinjaAPI(urls_namespace="analytics", title="Data Analytics API")
analytics_api.add_router("", analytics_router)
