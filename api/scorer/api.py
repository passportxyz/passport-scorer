"""
The scorer API module
"""
from ceramic_cache.api import router as ceramic_cache_router
from django.conf import settings
from ninja import NinjaAPI
from registry.api import router as registry_router
from registry.api import analytics_router

registry_api = NinjaAPI(urls_namespace="registry")
registry_api.add_router("/registry/", registry_router)

ceramic_cache_api = NinjaAPI(urls_namespace="ceramic-cache", docs_url=None)
ceramic_cache_api.add_router("", ceramic_cache_router)

analytics_api = NinjaAPI(urls_namespace="analytics", docs_url=None)
analytics_api.add_router("", analytics_router)
