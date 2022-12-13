from ninja import NinjaAPI
from registry.api import router as registry_router

api = NinjaAPI()

api.add_router("/registry/", registry_router)
