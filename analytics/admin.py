from django.contrib import admin

from analytics.models import CampaignRecord, DataSource


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("file_name", "status", "row_count", "uploaded_at")
    list_filter = ("status",)
    readonly_fields = ("uploaded_at",)


@admin.register(CampaignRecord)
class CampaignRecordAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "channel",
        "campaign_name",
        "impressions",
        "clicks",
        "cost",
        "conversions",
        "revenue",
        "data_source",
    )
    list_filter = ("channel", "date")
    search_fields = ("campaign_name",)
