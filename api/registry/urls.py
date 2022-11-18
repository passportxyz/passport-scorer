from django.urls import include, path
from rest_framework.routers import DefaultRouter

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
]
