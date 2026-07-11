from django.contrib import admin
from django.urls import include, path

from analytics.views import dashboard

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("analytics.urls")),
    path("", dashboard, name="dashboard"),
]
