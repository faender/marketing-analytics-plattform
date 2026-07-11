from django.db import models


class DataSource(models.Model):
    """A single uploaded CSV file and the outcome of ingesting it."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    file_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    row_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.file_name} ({self.status})"


class CampaignRecord(models.Model):
    """A single day/channel/campaign row of marketing performance data."""

    data_source = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name="records"
    )
    date = models.DateField()
    channel = models.CharField(max_length=100)
    campaign_name = models.CharField(max_length=255)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conversions = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["channel"]),
        ]

    def __str__(self):
        return f"{self.date} · {self.channel} · {self.campaign_name}"
