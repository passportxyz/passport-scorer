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
from account.api import health
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .api import (
    analytics_api,
    ceramic_cache_api,
    feature_flag_api,
    registry_api_v1,
    registry_api_v2,
)

urlpatterns = [
    path("", registry_api_v1.urls),
    path("registry/v2/", registry_api_v2.urls),
    path("registry/feature/", feature_flag_api.urls),
    path("ceramic-cache/", ceramic_cache_api.urls),
    path("analytics/", analytics_api.urls),
    path("health/", health, {}, "health-check"),
    path(
        "admin/login/",
        auth_views.LoginView.as_view(template_name="login.html"),
        name="login",
    ),
    path("admin/", admin.site.urls),
    path("account/", include("account.urls")),
    path("social/", include("social_django.urls", namespace="social")),
]
