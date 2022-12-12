"""scorer URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# from rest_framework.schemas import get_schema_view
from account.views import health
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("health/", health, {}, "health-check"),
    path("admin/", admin.site.urls),
    # path("api-auth/", include("rest_framework.urls")),
    path("registry/", include("registry.urls")),
    # path("scorer_weighted/", include("scorer_weighted.urls")),
    path("account/", include("account.urls")),
    # ...
    # Use the `get_schema_view()` helper to add a `SchemaView` to project URLs.
    #   * `title` and `description` parameters are passed to `SchemaGenerator`.
    #   * Provide view name for use with `reverse()`.
    # path(
    #     "openapi",
    #     get_schema_view(
    #         title="Your Project", description="API for all things …", version="1.0.0"
    #     ),
    #     name="openapi-schema",
    # ),
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
