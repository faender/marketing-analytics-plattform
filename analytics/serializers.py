from django.conf import settings
from rest_framework import serializers

from analytics.models import DataSource
from analytics.services.metrics import GRANULARITY_FREQ, METRIC_COLUMNS


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = ["id", "file_name", "uploaded_at", "row_count", "status", "error_message"]
        read_only_fields = fields


class CSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.lower().endswith(".csv"):
            raise serializers.ValidationError("File must be a .csv file.")
        if value.size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            raise serializers.ValidationError(f"File too large (max {max_mb:.0f} MB).")
        return value


class DateChannelFilterSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    channel = serializers.CharField(required=False)


class TrendsQuerySerializer(DateChannelFilterSerializer):
    granularity = serializers.ChoiceField(choices=list(GRANULARITY_FREQ), default="day")
    metric = serializers.ChoiceField(choices=METRIC_COLUMNS, default="revenue")


class TopCampaignsQuerySerializer(DateChannelFilterSerializer):
    metric = serializers.ChoiceField(choices=METRIC_COLUMNS, default="revenue")
    limit = serializers.IntegerField(required=False, default=5, min_value=1, max_value=50)
