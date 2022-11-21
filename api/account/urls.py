from .views import api
from django.urls import path

urlpatterns = [
    path("", api.urls),
]
