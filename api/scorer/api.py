"""
The scorer API module
"""
from ceramic_cache.api import router as ceramic_cache_router
from django.conf import settings
from ninja import NinjaAPI
from registry.api import router as registry_router

api = NinjaAPI()

api.add_router("/registry/", registry_router)

if settings.FEATURE_FLAG_DB_CACHE_API:
    api.add_router("/ceramic-cache/", ceramic_cache_router)
