from django.urls import path

from analytics import views

app_name = "analytics"

urlpatterns = [
    path("upload/", views.UploadView.as_view(), name="upload"),
    path("datasources/", views.DataSourceListView.as_view(), name="datasource-list"),
    path("metrics/summary/", views.MetricsSummaryView.as_view(), name="metrics-summary"),
    path("metrics/trends/", views.MetricsTrendsView.as_view(), name="metrics-trends"),
    path(
        "metrics/top-campaigns/",
        views.TopCampaignsView.as_view(),
        name="metrics-top-campaigns",
    ),
]
