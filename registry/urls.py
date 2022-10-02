from django.urls import include, path
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view

from . import views

# Create a router and register our viewsets with it.
router = DefaultRouter()
# router.register(r"submit-passport", views.PassportSubmit, basename="submit-passport")
router.register(r"passport", views.PassportViewSet, basename="passport")
router.register(r"stamp", views.StampViewSet, basename="stamp")

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path("", views.index),
    path("api/submit-passport/", views.submit_passport),
    path("api/", include(router.urls)),
    # ...
    # Use the `get_schema_view()` helper to add a `SchemaView` to project URLs.
    #   * `title` and `description` parameters are passed to `SchemaGenerator`.
    #   * Provide view name for use with `reverse()`.
    path(
        "openapi",
        get_schema_view(
            title="Your Project", description="API for all things …", version="1.0.0"
        ),
        name="openapi-schema",
    ),
    # ...
    # Route TemplateView to serve Swagger UI template.
    #   * Provide `extra_context` with view name of `SchemaView`.
    path(
        "swagger-ui/",
        TemplateView.as_view(
            template_name="registry/swagger-ui.html",
            extra_context={"schema_url": "openapi-schema"},
        ),
        name="swagger-ui",
    ),
]
