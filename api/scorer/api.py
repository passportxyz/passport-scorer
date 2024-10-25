# Update the following description:
# FROM: The V1 API docs are available at /v1/docs
# TO: Useful links:
# Developer Portal
# Developer docs
# Passport API V1 playground -- To be retired on April 4th, 2024
# Fix formatting for the new historical endpoint's description.
"""
The scorer API module
"""

from typing import List, Optional

from django_ratelimit.exceptions import Ratelimited
from ninja import NinjaAPI
from ninja.openapi.schema import OpenAPISchema
from ninja.operation import Operation
from ninja.types import DictStrAny

from ceramic_cache.api.v1 import router as ceramic_cache_router_v1
from passport_admin.api import router as passport_admin_router
from registry.api.utils import get_passport_api_rate_limited_msg
from registry.api.v1 import feature_flag_router
from registry.api.v1 import router as registry_router_v1


###############################################################################
# The following constructs will override the default OpenAPI schema generation
# The purpose if to enable adding a custom name to the security schema defined
# by an async function used in an async api.
# The default NinjaAPI implementation will use the name of the class or
# entity (which in case of a function is `function`), hence creating confusion
# (duplicate securitySchema Types) in the generated OpenAPI live docs.
# Our implementation will use the attribute `openapi_security_schema_name` of
# the auth object if it exists (this is our customisation), otherwise it will use
#  the class name (which is what NinjaAPI does right now).
###############################################################################
class ScorerOpenAPISchema(OpenAPISchema):
    def operation_security(self, operation: Operation) -> Optional[List[DictStrAny]]:
        if not operation.auth_callbacks:
            return None
        result = []
        for auth in operation.auth_callbacks:
            if hasattr(auth, "openapi_security_schema"):
                scopes: List[DictStrAny] = []  # TODO: scopes
                name = (
                    auth.openapi_security_schema_name
                    if hasattr(auth, "openapi_security_schema_name")
                    else auth.__class__.__name__
                )
                result.append({name: scopes})  # TODO: check if unique
                self.securitySchemes[name] = auth.openapi_security_schema  # type: ignore
        return result


def scorer_get_schema(api: "NinjaAPI", path_prefix: str = "") -> ScorerOpenAPISchema:
    openapi = ScorerOpenAPISchema(api, path_prefix)
    return openapi


###############################################################################
# End of customisinz securitySchema for OpenAPI
###############################################################################


registry_api_v1 = NinjaAPI(
    urls_namespace="registry",
    title="Passport API Playground.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/v1/openapi.json",
    description="""
The V2 (beta) API docs are available at [/v2/docs](/v2/docs)\n
The Passport Analysis endpoint is documented at [/passport/docs](/passport/docs)
""",
)


@registry_api_v1.exception_handler(Ratelimited)
def service_unavailable(request, _):
    return registry_api_v1.create_response(
        request,
        {"error": get_passport_api_rate_limited_msg()},
        status=429,
    )


registry_api_v1.add_router("/registry/", registry_router_v1, tags=["Passport API."])

feature_flag_api = NinjaAPI(urls_namespace="feature")
feature_flag_api.add_router("", feature_flag_router)


ceramic_cache_api_v1 = NinjaAPI(urls_namespace="ceramic-cache", docs_url=None)
ceramic_cache_api_v1.add_router("", ceramic_cache_router_v1)


passport_admin_api = NinjaAPI(urls_namespace="passport-admin", docs_url=None)
passport_admin_api.add_router("", passport_admin_router)

apis = [
    registry_api_v1,
    ceramic_cache_api_v1,
    passport_admin_api,
]
