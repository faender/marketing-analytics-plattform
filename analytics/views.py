from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.models import DataSource
from analytics.serializers import (
    CSVUploadSerializer,
    DataSourceSerializer,
    DateChannelFilterSerializer,
    TopCampaignsQuerySerializer,
    TrendsQuerySerializer,
)
from analytics.services import metrics as metrics_service
from analytics.services.ingestion import IngestionError, ingest_csv


class UploadView(APIView):
    """POST a CSV file; ingests it and returns the resulting DataSource."""

    def post(self, request):
        upload = CSVUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        uploaded_file = upload.validated_data["file"]

        data_source = DataSource.objects.create(file_name=uploaded_file.name)
        try:
            ingest_csv(uploaded_file, data_source)
        except IngestionError:
            return Response(
                DataSourceSerializer(data_source).data, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(DataSourceSerializer(data_source).data, status=status.HTTP_201_CREATED)


class DataSourceListView(generics.ListAPIView):
    """GET the upload history."""

    queryset = DataSource.objects.all()
    serializer_class = DataSourceSerializer


class MetricsSummaryView(APIView):
    """GET totals + derived averages (CTR/CPC/CPA/ROAS), optionally filtered."""

    def get(self, request):
        query = DateChannelFilterSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(metrics_service.get_summary(**query.validated_data))


class MetricsTrendsView(APIView):
    """GET a time series of one metric at day/week/month granularity."""

    def get(self, request):
        query = TrendsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        trends = metrics_service.get_trends(**query.validated_data)
        return Response({"trends": trends})


class TopCampaignsView(APIView):
    """GET the top N campaigns ranked by one metric."""

    def get(self, request):
        query = TopCampaignsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        top_campaigns = metrics_service.get_top_campaigns(**query.validated_data)
        return Response({"top_campaigns": top_campaigns})


def dashboard(request):
    # Fleshed out in Step 7 with KPI tiles, upload form, and the ask-box.
    return render(request, "analytics/dashboard.html")
